"""Tests for JPEG/RAW pair-adjacency ordering guarantees.

Validates that the sequencing logic in scripts 04, 09, and 10 never produces
runs like [jpeg1, jpeg2, raw1, raw2] — pairs must always be adjacent
([jpeg1, raw1, jpeg2, raw2]).
"""

import unittest
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Helpers extracted / mirrored from the pipeline scripts so we can unit-test
# the ordering logic without needing real image files on disk.
# ---------------------------------------------------------------------------

_KIND_ORDER = {'pair': 0, 'jpeg_single': 1, 'raw_single': 1, 'heic_single': 2}


def pair_lists(jpegs, raws):
    """Mirror of 09_build_chrono_pair_sequence.pair_lists."""
    used = set()
    pairs = []
    for j in jpegs:
        best_i = None
        best_dt = None
        for i, r in enumerate(raws):
            if i in used:
                continue
            delta = abs((j['dt'] - r['dt']).total_seconds())
            if best_dt is None or delta < best_dt:
                best_dt = delta
                best_i = i
        if best_i is not None:
            used.add(best_i)
            pairs.append((j, raws[best_i]))
    raw_un = [r for i, r in enumerate(raws) if i not in used]
    j_un = [j for j in jpegs if all(j is not p[0] for p in pairs)]
    return pairs, j_un, raw_un


def pair_nearest(jpegs, raws, max_delta_s=None):
    """Mirror of 10_rebuild_chrono_mated_prerotated.pair_nearest."""
    used = set()
    pairs = []
    for j in jpegs:
        best_i, best_delta = None, None
        for i, r in enumerate(raws):
            if i in used:
                continue
            d = abs((j['dt'] - r['dt']).total_seconds())
            if max_delta_s is not None and d > max_delta_s:
                continue
            if best_delta is None or d < best_delta:
                best_delta = d
                best_i = i
        if best_i is not None:
            used.add(best_i)
            pairs.append((j, raws[best_i]))
    j_un = [j for j in jpegs if all(j is not p[0] for p in pairs)]
    r_un = [r for i, r in enumerate(raws) if i not in used]
    return pairs, j_un, r_un


def build_events_09_style(buckets):
    """Simulate 09_build_chrono_pair_sequence event-building + sort.

    Each bucket value has 'jpeg', 'raw', 'heic' lists of dicts with 'dt',
    'orig', and 'src' keys.  Returns the ordered list of (role, orig) tuples
    representing the final frame sequence.
    """
    events = []
    for k, b in buckets.items():
        j = sorted(b.get('jpeg', []), key=lambda x: (x['dt'], x['orig']))
        r = sorted(b.get('raw', []), key=lambda x: (x['dt'], x['orig']))
        h = sorted(b.get('heic', []), key=lambda x: (x['dt'], x['orig']))

        pairs, j_un, r_un = pair_lists(j, r)

        for jj, rr in pairs:
            events.append({
                'dt': min(jj['dt'], rr['dt']),
                'kind': 'pair',
                'key': k,
                'items': [
                    {'role': 'jpeg', 'orig': jj['orig']},
                    {'role': 'raw', 'orig': rr['orig']},
                ],
            })

        # Interleaved singles (the fix)
        all_singles = [(x, 'jpeg') for x in j_un] + [(x, 'raw') for x in r_un]
        all_singles.sort(key=lambda s: (s[0]['dt'], s[0]['orig']))
        for x, role in all_singles:
            events.append({
                'dt': x['dt'],
                'kind': f'{role}_single',
                'key': k,
                'items': [{'role': role, 'orig': x['orig']}],
            })

        for x in h:
            events.append({
                'dt': x['dt'],
                'kind': 'heic_single',
                'key': k,
                'items': [{'role': 'heic', 'orig': x['orig']}],
            })

    events.sort(key=lambda e: (e['dt'], e['key'], _KIND_ORDER.get(e['kind'], 9)))

    sequence = []
    for ev in events:
        for it in ev['items']:
            sequence.append((it['role'], it['orig'], ev['kind']))
    return sequence


def _item(name, dt, src=None):
    """Shorthand for creating a file-item dict."""
    return {'orig': name, 'src': src or name, 'dt': dt}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScript04Interleave(unittest.TestCase):
    """Script 04: first JPEG paired with its RAW, then remaining JPEGs."""

    @staticmethod
    def _build_seq_04(jpg_map, raw_rendered):
        """Simulate the fixed 04 logic."""
        sequence = []
        for k in sorted(jpg_map.keys()):
            jpegs = sorted(jpg_map[k])
            raw = raw_rendered.get(k)
            if raw and jpegs:
                sequence.append(jpegs[0])
                sequence.append(raw)
                for j in jpegs[1:]:
                    sequence.append(j)
            else:
                for j in jpegs:
                    sequence.append(j)
        return sequence

    def test_single_jpeg_single_raw(self):
        seq = self._build_seq_04({'photo': ['j1']}, {'photo': 'r1'})
        self.assertEqual(seq, ['j1', 'r1'])

    def test_two_jpegs_one_raw(self):
        """Bug case: two JPEGs must not both appear before the RAW."""
        seq = self._build_seq_04({'photo': ['j1', 'j2']}, {'photo': 'r1'})
        # j1 paired with r1 first, then j2 alone
        self.assertEqual(seq, ['j1', 'r1', 'j2'])

    def test_three_jpegs_one_raw(self):
        seq = self._build_seq_04({'photo': ['j1', 'j2', 'j3']}, {'photo': 'r1'})
        self.assertEqual(seq, ['j1', 'r1', 'j2', 'j3'])

    def test_no_raw(self):
        seq = self._build_seq_04({'photo': ['j1', 'j2']}, {})
        self.assertEqual(seq, ['j1', 'j2'])


class TestPairLists(unittest.TestCase):
    """pair_lists greedy nearest-timestamp pairing."""

    def test_basic_pairing(self):
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        j = [_item('j1', t0)]
        r = [_item('r1', t0)]
        pairs, j_un, r_un = pair_lists(j, r)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(len(j_un), 0)
        self.assertEqual(len(r_un), 0)

    def test_two_pairs_same_time(self):
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        j = [_item('j1', t0), _item('j2', t0)]
        r = [_item('r1', t0), _item('r2', t0)]
        pairs, j_un, r_un = pair_lists(j, r)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(len(j_un), 0)
        self.assertEqual(len(r_un), 0)

    def test_unequal_counts(self):
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        j = [_item('j1', t0), _item('j2', t0), _item('j3', t0)]
        r = [_item('r1', t0)]
        pairs, j_un, r_un = pair_lists(j, r)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(len(j_un), 2)
        self.assertEqual(len(r_un), 0)


class TestPairNearest(unittest.TestCase):
    """pair_nearest with optional max_delta_s."""

    def test_within_delta(self):
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        t1 = t0 + timedelta(seconds=2)
        j = [_item('j1', t0)]
        r = [_item('r1', t1)]
        pairs, _, _ = pair_nearest(j, r, max_delta_s=3.0)
        self.assertEqual(len(pairs), 1)

    def test_exceeds_delta(self):
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        t1 = t0 + timedelta(seconds=5)
        j = [_item('j1', t0)]
        r = [_item('r1', t1)]
        pairs, j_un, r_un = pair_nearest(j, r, max_delta_s=3.0)
        self.assertEqual(len(pairs), 0)
        self.assertEqual(len(j_un), 1)
        self.assertEqual(len(r_un), 1)


class TestEventSortOrder(unittest.TestCase):
    """Verify the fixed sort key prevents pair-splitting by singles."""

    def test_pair_before_single_same_timestamp(self):
        """A jpeg_single at the same (dt, key) must NOT sort before a pair."""
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        buckets = {
            'bucket_a': {
                'jpeg': [_item('j1', t0), _item('j2', t0)],
                'raw': [_item('r1', t0)],
                'heic': [],
            }
        }
        seq = build_events_09_style(buckets)
        roles = [s[0] for s in seq]
        # pair_lists pairs j1-r1; j2 is unpaired.
        # With the fix, pair event (j1, r1) sorts before jpeg_single (j2).
        self.assertEqual(roles, ['jpeg', 'raw', 'jpeg'])

    def test_two_pairs_stay_interleaved(self):
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        buckets = {
            'bucket_a': {
                'jpeg': [_item('j1', t0), _item('j2', t0)],
                'raw': [_item('r1', t0), _item('r2', t0)],
                'heic': [],
            }
        }
        seq = build_events_09_style(buckets)
        roles = [s[0] for s in seq]
        # Two pair events → j, r, j, r
        self.assertEqual(roles, ['jpeg', 'raw', 'jpeg', 'raw'])

    def test_singles_interleaved_by_time(self):
        """Unpaired singles must interleave by timestamp, not cluster by type."""
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        t1 = t0 + timedelta(seconds=1)
        t2 = t0 + timedelta(seconds=2)
        t3 = t0 + timedelta(seconds=3)
        # 2 jpegs + 2 raws, but in different buckets so pairing can't happen
        buckets = {
            'bucket_a': {
                'jpeg': [_item('j1', t0), _item('j2', t2)],
                'raw': [],
                'heic': [],
            },
            'bucket_b': {
                'jpeg': [],
                'raw': [_item('r1', t1), _item('r2', t3)],
                'heic': [],
            },
        }
        seq = build_events_09_style(buckets)
        roles = [s[0] for s in seq]
        # Chronological: j1(t0), r1(t1), j2(t2), r2(t3)
        self.assertEqual(roles, ['jpeg', 'raw', 'jpeg', 'raw'])

    def test_no_pair_adjacency_violations(self):
        """Run the validation logic on a complex scenario."""
        t0 = datetime(2024, 1, 1, 10, 0, 0)
        buckets = {
            'bucket_a': {
                'jpeg': [
                    _item('j1', t0),
                    _item('j2', t0 + timedelta(seconds=1)),
                    _item('j3', t0 + timedelta(seconds=2)),
                ],
                'raw': [_item('r1', t0)],
                'heic': [],
            }
        }
        seq = build_events_09_style(buckets)
        # build_events_09_style now returns (role, orig, event_kind) tuples;
        # use event_kind directly instead of inferring it from position.
        audit = [{'role': role, 'event_kind': kind, 'index': i}
                 for i, (role, _orig, kind) in enumerate(seq)]

        violations = []
        for i in range(len(audit) - 1):
            a, b = audit[i], audit[i + 1]
            if (a['role'] == b['role']
                    and a['role'] in ('jpeg', 'raw')
                    and ('pair' in a['event_kind'] or 'pair' in b['event_kind'])):
                violations.append((a['index'], b['index']))
        self.assertEqual(violations, [], f"Pair-adjacency violations: {violations}")


class TestKindOrderGuarantee(unittest.TestCase):
    """Verify that the _KIND_ORDER mapping produces the intended sort."""

    def test_pair_sorts_before_jpeg_single(self):
        self.assertLess(_KIND_ORDER['pair'], _KIND_ORDER['jpeg_single'])

    def test_pair_sorts_before_raw_single(self):
        self.assertLess(_KIND_ORDER['pair'], _KIND_ORDER['raw_single'])

    def test_jpeg_and_raw_singles_same_priority(self):
        self.assertEqual(_KIND_ORDER['jpeg_single'], _KIND_ORDER['raw_single'])


if __name__ == '__main__':
    unittest.main()
