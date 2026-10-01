"""Run the production non-Linux audio unit tests without opening audio devices."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PLAYBACK_TESTS = (
    'writing_audio_observes_discard_and_releases_buffer_lock',
    'smooths_underflow_and_explicit_audio_discontinuities',
    'validates_configuration_and_frame_size',
    'playback_contention_preserves_queued_audio_and_recovers_after_release',
    'poisoned_playback_buffer_reports_once_without_panicking_in_the_callback',
    'contention_counts_accumulate_until_the_next_report',
    'contention_reporting_is_independent_between_playbacks',
)
BUFFER_TESTS = (
    'overwrite_and_partial_reads_match_fifo_across_wraps',
    'empty_input_preserves_pending_pcm_and_generation',
    'overwrite_keeps_stereo_order_for_oversized_packets',
    'unchanged_capacity_preserves_pending_pcm_and_shared_handles',
    'changed_capacity_clears_pcm_without_replacing_shared_handles',
    'overflow_generation_wraps_without_changing_sample_order',
    'repeated_producer_overwrite_reuses_allocated_storage',
)
RECOVERY_TESTS = (
    'unconfirmed_start_retries_without_callback_or_error',
    'already_terminal_candidate_cannot_replace_compatible_output',
    'pending_output_keeps_playing_and_transfers_decoder_history_on_commit',
    'rollback_keeps_the_restarted_decoders_accumulated_history',
    'later_compatible_format_retires_only_the_pending_attempt',
    'both_outputs_failing_retains_format_and_paces_recovery',
    'superseding_format_keeps_ready_candidate_when_active_output_failed',
    'superseding_format_preserves_failure_when_both_outputs_failed',
)
ALLOCATION_TEST = 'audio_resampler::allocation_tests::capture_resampling_reuses_buffers'


def required_tests(system: str) -> set[str]:
    if system not in ('Windows', 'Darwin'):
        raise ValueError('Playback contracts require a native Windows or macOS host')
    tests = {f'client::audio_playback::tests::{name}' for name in PLAYBACK_TESTS}
    tests.update(f'client::audio_buffer_contract_tests::{name}' for name in BUFFER_TESTS)
    tests.add('client::audio_buffer_discontinuity_tests::capacity_discards_signal_discontinuities')
    tests.add('client::audio_state_tests::identical_format_failure_preserves_playback_and_resampler_history')
    if system == 'Windows':
        tests.update(f'client::audio_state_tests::recovery_tests::{name}' for name in RECOVERY_TESTS)
    return tests


def check_results(text: str, required: set[str]) -> list[str]:
    results = re.findall(r'^test ([\w:]+) \.\.\. (ok|FAILED|ignored)\s*$', text, re.MULTILINE)
    summaries = re.findall(
        r'^test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured;',
        text, re.MULTILINE,
    )
    passed = [name for name, status in results if status == 'ok']
    if len(summaries) != 1 or tuple(map(int, summaries[0])) != (len(passed), 0, 0, 0):
        raise ValueError('Missing, failed or inconsistent Rust test summary')
    if len(passed) != len(results) or len(passed) != len(set(passed)) or not required.issubset(passed):
        raise ValueError('Required production audio tests did not all pass')
    return sorted(passed)


def run_tests(root: Path, test_filter: str, log: Path, required: set[str]) -> list[str]:
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(
            ['cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter',
             test_filter, '--', '--test-threads=1'],
            cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=1200, check=False,
        )
    text = log.read_text(encoding='utf-8', errors='replace')
    if result.returncode:
        print('\n'.join(text.splitlines()[-100:]), file=sys.stderr)
        raise RuntimeError(f'Audio test command failed ({result.returncode}); see {log}')
    return check_results(text, required)


def validate(root: Path = ROOT) -> dict:
    system = platform.system()
    required = required_tests(system)
    reports = root / 'tools/.reports'
    if reports.is_symlink():
        raise ValueError('Reports directory must not be a symlink')
    reports.mkdir(parents=True, exist_ok=True)
    paths = [reports / name for name in ('audio-contracts.json', 'audio-playback-tests.log', 'audio-allocation-tests.log')]
    if any(path.is_symlink() for path in paths):
        raise ValueError('Audio evidence must not be a symlink')
    evidence, playback_log, allocation_log = paths
    evidence.unlink(missing_ok=True)
    before = hashlib.sha256((root / 'Cargo.lock').read_bytes()).hexdigest()
    locked = tomllib.loads((root / 'Cargo.lock').read_text(encoding='utf-8'))
    rings = [item['version'] for item in locked['package'] if item['name'] == 'ringbuf']
    if len(rings) != 1:
        raise ValueError('Expected one resolved ringbuf dependency')
    playback = run_tests(root, 'client::audio', playback_log, required)
    allocations = run_tests(root, ALLOCATION_TEST, allocation_log, {ALLOCATION_TEST})
    if hashlib.sha256((root / 'Cargo.lock').read_bytes()).hexdigest() != before:
        raise ValueError('Audio tests changed Cargo.lock')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a complete source revision')
    report = {'revision': revision, 'system': system, 'architecture': platform.machine(),
              'ringbuf': rings[0], 'cargo_lock_sha256': before,
              'playback_tests': playback, 'allocation_tests': allocations,
              'device_audio': 'not-executed', 'remote_audio_session': 'not-verified'}
    evidence.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Passed {len(playback)} production playback tests and {len(allocations)} capture allocation test on {system}')
    return report


if __name__ == '__main__':
    try:
        validate()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print(f'Audio validation failed: {error}', file=sys.stderr)
        raise SystemExit(1)
