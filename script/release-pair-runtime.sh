#!/usr/bin/env bash
# Controlled WordPress/MySQL release-pair smoke, never a production deployment.
set -euo pipefail

root="$1"
test -n "$root"
cd "$root"
test -f receipt.json && test -f .wp-env.json
plugin_slug="$(python3 -c 'import json;print(json.load(open("receipt.json"))["plugin_slug"])')"
theme_slug="$(python3 -c 'import json;print(json.load(open("receipt.json"))["theme_slug"])')"
upgrade="$(python3 -c 'import json;print("yes" if json.load(open("receipt.json"))["upgrade_mode"] else "no")')"
mkdir -p evidence

wp-env start
wp-env run cli wp core is-installed
wp-env run cli wp theme activate "$theme_slug"
wp-env run cli wp plugin activate "$plugin_slug"
wp-env run cli wp --skip-plugins --skip-themes plugin is-active "$plugin_slug"
wp-env run cli wp --skip-plugins --skip-themes eval 'if (! $GLOBALS["wpdb"]->check_connection(false)) { exit(8); } echo "DATABASE_OK\n";'
wp-env run cli wp --skip-plugins --skip-themes core version > evidence/wordpress-version.txt
wp-env run cli wp --skip-plugins --skip-themes eval 'echo $GLOBALS["wpdb"]->get_var("SELECT VERSION()") . PHP_EOL;' > evidence/mariadb-version.txt
wp-env run cli wp --skip-plugins --skip-themes eval 'echo PHP_VERSION . PHP_EOL;' > evidence/php-version.txt

# Synthetic editor-authored content; not customer data.
wp-env run cli wp --skip-plugins --skip-themes eval '
$id = wp_insert_post(array(
    "post_type" => "page",
    "post_status" => "draft",
    "post_title" => "Release pair preservation sentinel",
    "post_content" => "This is isolated test content."
));
if (is_wp_error($id) || ! $id) { exit(9); }
update_post_meta($id, "_release_pair_preserve", "keep");
update_option("_release_pair_test_post_id", $id, false);
'
if [[ "$upgrade" == "yes" ]]; then
    wp-env run cli wp plugin deactivate "$plugin_slug"
    python3 ../harness/script/release-pair-prepare.py promote --output .
    wp-env run cli wp plugin activate "$plugin_slug"
    wp-env run cli wp plugin deactivate "$plugin_slug"
    wp-env run cli wp plugin activate "$plugin_slug"
fi
# The submitted plugin/theme must not execute while verifying its own state.
verify_release_state() {
  wp-env run cli wp --skip-plugins --skip-themes plugin is-active "$plugin_slug"
  wp-env run cli wp --skip-plugins --skip-themes theme is-active "$theme_slug"
  wp-env run cli wp --skip-plugins --skip-themes eval '
$id = (int) get_option("_release_pair_test_post_id");
$post = get_post($id);
if (! $post || $post->post_title !== "Release pair preservation sentinel") { exit(10); }
if ($post->post_status !== "draft") { exit(12); }
if ($post->post_content !== "This is isolated test content.") { exit(13); }
if (get_post_meta($id, "_release_pair_preserve", true) !== "keep") { exit(11); }
echo "POST_AND_META_PRESERVED\n";
'
}

verify_release_state

# Reject all redirects: a remote 200 must not masquerade as a healthy local WP frontend.
curl --fail --location --max-redirs 0 --silent --show-error --max-time 30 \
    --output /dev/null "http://127.0.0.1:$WP_ENV_PORT/"
# Frontend hooks may mutate data/theme state; the second unfiltered DB read catches it.
verify_release_state
printf 'wp_bootstrap=passed\ntheme_active=passed\nplugin_active=passed\nsynthetic_content=preserved\n' > evidence/runtime-summary.txt
if [[ "$upgrade" == "yes" ]]; then
    printf 'upgrade_and_repeat_activation=passed\n' >> evidence/runtime-summary.txt
else
    printf 'upgrade_and_repeat_activation=not_run_no_previous_archive\n' >> evidence/runtime-summary.txt
fi
