#!/usr/bin/env bash
set -uo pipefail

: "${PLUGIN_DIR:?PLUGIN_DIR is required}"

RESULTS="${GITHUB_WORKSPACE:-$PWD}/audit-results"
RUNTIME_ROOT="${RUNNER_TEMP:-/tmp}/programmeren-runtime-${GITHUB_RUN_ID:-$$}"
WP_DIR="$RUNTIME_ROOT/wordpress"
PLUGIN_COPY="$WP_DIR/wp-content/plugins/audit-target"
BASE_URL="http://127.0.0.1:8881"
STATUS="$RESULTS/integration-status.tsv"
SERVER_PID=""
FAILURES=0

mkdir -p "$RESULTS" "$RUNTIME_ROOT"
printf 'check\tstatus\texit_code\n' > "$STATUS"

cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    rm -f "$WP_DIR/wp-content/mu-plugins/programmeren-provider-mock.php" 2>/dev/null || true
}
trap cleanup EXIT

record() {
    local name="$1" status="$2" code="$3"
    printf '%s\t%s\t%s\n' "$name" "$status" "$code" >> "$STATUS"
    if [[ "$status" == "FAIL" ]]; then
        FAILURES=$((FAILURES + 1))
    fi
}

run_check() {
    local name="$1"; shift
    local log="$RESULTS/integration-${name}.log"
    echo "::group::integration:${name}"
    set +e
    "$@" > >(tee "$log") 2>&1
    local code=$?
    set -e
    if [[ $code -eq 0 ]]; then
        record "$name" PASS 0
    else
        record "$name" FAIL "$code"
    fi
    echo "::endgroup::"
    return 0
}

wait_mysql() {
    php -r '
        $deadline = microtime(true) + 90;
        do {
            mysqli_report(MYSQLI_REPORT_OFF);
            $db = @new mysqli("127.0.0.1", "wordpress", "wordpress", "wordpress", 3306);
            if (!$db->connect_errno) { echo "mysql=ready\n"; exit(0); }
            usleep(500000);
        } while (microtime(true) < $deadline);
        fwrite(STDERR, "mysql did not become ready\n"); exit(1);
    '
}

wait_redis() {
    php -r '
        if (!class_exists("Redis")) { fwrite(STDERR, "phpredis missing\n"); exit(2); }
        $deadline = microtime(true) + 60;
        do {
            try {
                $r = new Redis();
                if ($r->connect("127.0.0.1", 6379, 1.0) && $r->ping()) { echo "redis=ready\n"; $r->close(); exit(0); }
            } catch (Throwable $e) {}
            usleep(500000);
        } while (microtime(true) < $deadline);
        fwrite(STDERR, "redis did not become ready\n"); exit(1);
    '
}

copy_target() {
    rm -rf "$PLUGIN_COPY"
    mkdir -p "$PLUGIN_COPY"
    cp -a "$PLUGIN_DIR"/. "$PLUGIN_COPY"/
}

wp_cmd() {
    wp --path="$WP_DIR" --allow-root "$@"
}

start_server() {
    cat > "$RUNTIME_ROOT/router.php" <<PHP
<?php
\$path = parse_url(\$_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
\$file = rtrim('${WP_DIR}', '/') . \$path;
if ('/' !== \$path && is_file(\$file)) { return false; }
require '${WP_DIR}/index.php';
PHP
    php -S 127.0.0.1:8881 -t "$WP_DIR" "$RUNTIME_ROOT/router.php" > "$RESULTS/integration-php-server.log" 2>&1 &
    SERVER_PID=$!
    for _ in $(seq 1 60); do
        if curl -fsS "$BASE_URL/" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

write_provider_mock() {
    mkdir -p "$WP_DIR/wp-content/mu-plugins"
    cat > "$WP_DIR/wp-content/mu-plugins/programmeren-provider-mock.php" <<'PHP'
<?php
add_filter('pre_http_request', static function ($pre, $args, $url) {
    if (false === strpos((string) $url, 'api.cloudflare.com/client/v4/')) return $pre;
    $mode = (string) get_option('programmeren_provider_mode', 'success');
    if ('timeout' === $mode) return new WP_Error('http_request_failed', 'programmeren simulated timeout');
    $code = '429' === $mode ? 429 : ('500' === $mode ? 500 : 200);
    $body = 'oversize' === $mode ? str_repeat('x', 70000) : wp_json_encode(array('success' => 200 === $code, 'mode' => $mode));
    return array('headers'=>array('content-type'=>'application/json'),'body'=>$body,'response'=>array('code'=>$code,'message'=>200===$code?'OK':'Simulated failure'),'cookies'=>array(),'filename'=>null);
}, 10, 3);
PHP
}

{
    echo "php=$(php -r 'echo PHP_VERSION;')"
    php -m | sort | sed 's/^/php_ext=/'
    wp --version
    node --version || true
    npm --version || true
} > "$RESULTS/integration-tool-versions.txt" 2>&1

run_check "required-extensions" php -r '$required=["mysqli","redis","apcu"];$missing=array_values(array_filter($required,fn($e)=>!extension_loaded($e)));if($missing){fwrite(STDERR,"missing=".implode(",",$missing)."\n");exit(1);}if(!filter_var(ini_get("apc.enabled"),FILTER_VALIDATE_BOOLEAN)){fwrite(STDERR,"APCu disabled\n");exit(1);}echo "extensions=ok\n";'
run_check "mysql-service" wait_mysql
run_check "redis-service" wait_redis
if (( FAILURES > 0 )); then exit 1; fi

run_check "wordpress-download" wp core download --path="$WP_DIR" --force
run_check "wordpress-config" wp config create --path="$WP_DIR" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress --dbhost=127.0.0.1:3306 --skip-check --force
wp_cmd config set WP_DEBUG true --raw >/dev/null
wp_cmd config set WP_DEBUG_LOG true --raw >/dev/null
wp_cmd config set WP_DEBUG_DISPLAY false --raw >/dev/null
wp_cmd config set WP_REDIS_HOST 127.0.0.1 >/dev/null
wp_cmd config set WP_REDIS_PORT 6379 --raw >/dev/null
wp_cmd config set WP_REDIS_TIMEOUT 1.0 --raw >/dev/null
run_check "wordpress-install" wp core install --path="$WP_DIR" --url="$BASE_URL" --title="Programmeren Audit" --admin_user=admin --admin_password='audit-admin-password' --admin_email=admin@example.test --skip-email
run_check "mysql-wordpress-query" wp_cmd eval 'global $wpdb;$v=$wpdb->get_var("SELECT 1");echo "select=".$v."\n";exit("1"===(string)$v?0:1);'
run_check "pretty-permalinks" wp_cmd rewrite structure '/%postname%/' --hard

copy_target
run_check "activate-without-woocommerce" wp_cmd plugin activate audit-target
run_check "deactivate-without-woocommerce" wp_cmd plugin deactivate audit-target
run_check "woocommerce-install" wp_cmd plugin install woocommerce --activate
copy_target
run_check "activate-with-woocommerce" wp_cmd plugin activate audit-target

{ wp_cmd core version | sed 's/^/wordpress=/'; wp_cmd plugin get audit-target --field=version | sed 's/^/target_plugin=/'; wp_cmd plugin get woocommerce --field=version | sed 's/^/woocommerce=/'; php -r 'echo "redis_ext=".phpversion("redis").PHP_EOL;echo "apcu_ext=".phpversion("apcu").PHP_EOL;'; } > "$RESULTS/integration-runtime-versions.txt" 2>&1

run_check "server-start" start_server
if (( FAILURES == 0 )); then
    run_check "homepage-http" curl -fsS -o "$RESULTS/integration-homepage.html" -D "$RESULTS/integration-homepage.headers" "$BASE_URL/"
    run_check "rest-index-http" curl -fsS -o "$RESULTS/integration-rest-index.json" -D "$RESULTS/integration-rest-index.headers" "$BASE_URL/wp-json/"
fi

PRODUCT_ID=""
set +e
PRODUCT_ID="$(wp_cmd eval '$p=new WC_Product_Simple();$p->set_name("Programmeren Audit Product");$p->set_status("publish");$p->set_regular_price("9.99");echo $p->save();' 2>>"$RESULTS/integration-woocommerce-product.log")"
PRODUCT_CODE=$?
set -e
if [[ $PRODUCT_CODE -eq 0 && "$PRODUCT_ID" =~ ^[0-9]+$ && "$PRODUCT_ID" -gt 0 ]]; then echo "product_id=$PRODUCT_ID" > "$RESULTS/integration-woocommerce-product.log"; record "woocommerce-product" PASS 0; else record "woocommerce-product" FAIL "${PRODUCT_CODE:-1}"; fi

if [[ -n "$PRODUCT_ID" && "$PRODUCT_ID" =~ ^[0-9]+$ ]]; then
    set +e; curl -fsS -D "$RESULTS/integration-store-cart.headers" -o "$RESULTS/integration-store-cart.json" "$BASE_URL/wp-json/wc/store/v1/cart"; CART_CODE=$?; set -e
    if [[ $CART_CODE -eq 0 ]]; then
        record "woocommerce-store-cart" PASS 0
        CART_TOKEN="$(awk 'BEGIN{IGNORECASE=1} /^Cart-Token:/ {sub(/^[^:]+:[[:space:]]*/,"");sub(/\r$/,"");print;exit}' "$RESULTS/integration-store-cart.headers")"
        if [[ -n "$CART_TOKEN" ]]; then
            set +e; curl -fsS -X POST -H "Content-Type: application/json" -H "Cart-Token: $CART_TOKEN" --data "{\"id\":${PRODUCT_ID},\"quantity\":1}" -D "$RESULTS/integration-store-add-item.headers" -o "$RESULTS/integration-store-add-item.json" "$BASE_URL/wp-json/wc/store/v1/cart/add-item"; ADD_CODE=$?; set -e
            [[ $ADD_CODE -eq 0 ]] && record "woocommerce-store-add-item" PASS 0 || record "woocommerce-store-add-item" FAIL "$ADD_CODE"
        else record "woocommerce-store-add-item" FAIL 2; fi
    else record "woocommerce-store-cart" FAIL "$CART_CODE"; fi
fi

run_check "cron-list" wp_cmd cron event list --format=json
run_check "cron-due" wp_cmd cron event run --due-now

if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    set +e; : > "$RESULTS/integration-concurrency.tsv"
    for path in / /wp-json/ /shop/ /cart/; do seq 1 12 | xargs -P 6 -I{} sh -c 'code=$(curl -sS -o /dev/null -w "%{http_code}" "$1" || printf 000);printf "%s\t%s\n" "$1" "$code"' _ "$BASE_URL$path" >> "$RESULTS/integration-concurrency.tsv"; done
    BAD_HTTP="$(awk '$2 ~ /^5/ || $2 == "000" {count++} END {print count+0}' "$RESULTS/integration-concurrency.tsv")"; set -e
    [[ "$BAD_HTTP" -eq 0 ]] && record "concurrency-http" PASS 0 || record "concurrency-http" FAIL 1
fi

if wp_cmd eval 'exit(class_exists("UCP_Object_Cache")?0:3);' >/dev/null 2>&1; then
    run_check "ucp-object-cache-capabilities" wp_cmd eval '$s=UCP_Object_Cache::status(true);echo wp_json_encode($s,JSON_PRETTY_PRINT)."\n";$ok=!empty($s["redis_connected"])&&!empty($s["apcu_available"]);exit($ok?0:1);'
    run_check "ucp-redis-dropin-install" wp_cmd eval '$m=new ReflectionMethod("UCP_Object_Cache","write_dropin");$m->setAccessible(true);$r=$m->invoke(null,"redis");if(is_wp_error($r)){fwrite(STDERR,$r->get_error_code()."\n");exit(1);}exit($r===true?0:1);'
    run_check "ucp-redis-dropin-runtime" wp_cmd eval 'if(!wp_using_ext_object_cache())exit(1);wp_cache_set("programmeren_probe","redis-ok","programmeren",60);$v=wp_cache_get("programmeren_probe","programmeren");echo "value=".$v."\n";exit("redis-ok"===$v?0:1);'
    run_check "ucp-redis-dropin-remove" wp_cmd eval '$r=UCP_Object_Cache::remove_owned_dropin();exit(is_wp_error($r)?1:0);'
    run_check "ucp-apcu-dropin-install" wp_cmd eval '$m=new ReflectionMethod("UCP_Object_Cache","write_dropin");$m->setAccessible(true);$r=$m->invoke(null,"apcu");if(is_wp_error($r)){fwrite(STDERR,$r->get_error_code()."\n");exit(1);}exit($r===true?0:1);'
    run_check "ucp-apcu-dropin-runtime" wp_cmd eval 'if(!wp_using_ext_object_cache())exit(1);wp_cache_set("programmeren_probe","apcu-ok","programmeren",60);$v=wp_cache_get("programmeren_probe","programmeren");echo "value=".$v."\n";exit("apcu-ok"===$v?0:1);'
    run_check "ucp-apcu-dropin-remove" wp_cmd eval '$r=UCP_Object_Cache::remove_owned_dropin();exit(is_wp_error($r)?1:0);'
    if wp_cmd eval 'exit(class_exists("UCP_Runtime_Tests")?0:3);' >/dev/null 2>&1; then
        set +e; wp_cmd eval '$r=UCP_Runtime_Tests::run_all();echo wp_json_encode($r,JSON_PRETTY_PRINT)."\n";foreach($r as $v){if(is_array($v)&&isset($v["status"])&&"fail"===$v["status"])exit(1);}exit(0);' > "$RESULTS/integration-ucp-runtime-suite.json" 2> "$RESULTS/integration-ucp-runtime-suite.err"; UCP_SUITE_CODE=$?; set -e
        [[ $UCP_SUITE_CODE -eq 0 ]] && record "ucp-runtime-suite" PASS 0 || record "ucp-runtime-suite" FAIL "$UCP_SUITE_CODE"
    fi
    write_provider_mock
    run_check "ucp-provider-mock" wp_cmd eval 'UCP_Options::update(array("cloudflare_zone_id"=>str_repeat("a",32),"cloudflare_api_token"=>"programmeren-audit-secret"));$cases=array("success"=>true,"429"=>false,"500"=>false,"timeout"=>false,"oversize"=>false);foreach($cases as $mode=>$expected){update_option("programmeren_provider_mode",$mode,false);$got=UCP_Edge::cloudflare_purge_all();echo $mode."=".($got?"true":"false")."\n";if($got!==$expected)exit(1);}exit(0);'
    if grep -RIl --binary-files=without-match 'programmeren-audit-secret' "$WP_DIR/wp-content" "$RESULTS" 2>/dev/null | grep -v 'integration-ucp-provider-mock.log' > "$RESULTS/integration-secret-leak-files.txt"; then record "ucp-provider-secret-redaction" FAIL 1; else record "ucp-provider-secret-redaction" PASS 0; fi
    rm -f "$WP_DIR/wp-content/mu-plugins/programmeren-provider-mock.php"
fi

if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    mkdir -p "$RUNTIME_ROOT/browser"; cp "${GITHUB_WORKSPACE:-$PWD}/.audit/runtime/browser-smoke.spec.js" "$RUNTIME_ROOT/browser/browser-smoke.spec.js"; pushd "$RUNTIME_ROOT/browser" >/dev/null; npm init -y >/dev/null 2>&1
    run_check "playwright-package" npm install --save-exact --no-audit --no-fund @playwright/test@1.62.1
    if grep -q $'^playwright-package\tPASS' "$STATUS"; then run_check "playwright-browser-install" npx playwright install chromium --with-deps; BASE_URL="$BASE_URL" PLAYWRIGHT_SCREENSHOT="$RESULTS/integration-browser-home.png" run_check "browser-smoke" npx playwright test browser-smoke.spec.js --reporter=line --workers=1; fi
    popd >/dev/null
fi

run_check "plugin-deactivate-final" wp_cmd plugin deactivate audit-target
run_check "plugin-uninstall" wp_cmd plugin uninstall audit-target
if [[ -f "$WP_DIR/wp-content/debug.log" ]]; then cp "$WP_DIR/wp-content/debug.log" "$RESULTS/integration-wp-debug.log"; else : > "$RESULTS/integration-wp-debug.log"; fi
if grep -Eiq 'PHP (Fatal error|Parse error)|Uncaught (Error|Exception)|Allowed memory size .* exhausted' "$RESULTS/integration-wp-debug.log" "$RESULTS/integration-php-server.log"; then record "runtime-fatal-scan" FAIL 1; else record "runtime-fatal-scan" PASS 0; fi

python3 - "$STATUS" "$RESULTS/integration-summary.json" <<'PY'
import csv,json,sys
status_path,out=sys.argv[1:]
rows=list(csv.DictReader(open(status_path,encoding='utf-8'),delimiter='\t'))
summary={'schema_version':'1.0','evidence_level':'controlled_runtime','checks':rows,'pass':sum(r['status']=='PASS' for r in rows),'fail':sum(r['status']=='FAIL' for r in rows)}
open(out,'w',encoding='utf-8').write(json.dumps(summary,indent=2)+'\n')
PY

if (( FAILURES > 0 )); then echo "Ephemeral integration runtime completed with ${FAILURES} failing check(s)." >&2; exit 1; fi
echo "Ephemeral integration runtime passed."
