<?php
/**
 * Plugin Name: Programmeren Audit Fixture
 * Description: Minimal safe plugin used only to validate the central audit harness.
 * Version: 1.0.0
 * Requires at least: 6.8
 * Requires PHP: 7.4
 * Author: Webactueel
 * License: GPL-2.0-or-later
 * Text Domain: programmeren-audit-fixture
 *
 * @package ProgrammerenAuditFixture
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Return the fixture status.
 *
 * @return string
 */
function programmeren_audit_fixture_status() {
	return 'ok';
}
