'''Focused tests for the pure clock-time overview series helpers.'''

import json
import os
import re

import pytest

quickjs = pytest.importorskip('quickjs')
JS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                       'public', 'assets', 'js',
                                       'kiln-controller.js'))


def extract_function(src, name):
    match = re.search(r'\nfunction %s\([^)]*\)\s*\{' % re.escape(name), src)
    assert match, 'function %s not found' % name
    start = match.end() - 1
    depth = 1
    i = start + 1
    while depth:
        depth += (src[i] == '{') - (src[i] == '}')
        i += 1
    return src[match.start():i]


@pytest.fixture(scope='module')
def js():
    src = open(JS_PATH).read()
    context = quickjs.Context()
    for name in ('clockSampleTime', 'clockUniqueSamples',
                 'clockElapsedSeconds',
                 'clockMeasuredSeries', 'clockProfileValue',
                 'clockIdealSeries', 'clockShiftedHistorySeries',
                 'clockShiftedFutureSeries', 'buildClockTimeSeries'):
        context.eval(extract_function(src, name))
    return context


def value(js, expression):
    return json.loads(js.eval('JSON.stringify(%s)' % expression))


PROFILE = '[[0,100],[10,200],[20,300],[30,400],[40,500]]'


def test_multiple_catchups_are_piecewise_and_history_is_immutable(js):
    # A-E are sampled at wall epochs 1000, 1010, 1025, 1035, 1050.  The
    # gaps at 1010-1025 and 1035-1050 are two separate catch-up periods.
    early_samples = ('[{time:1000,ispoint:100,setpoint:100},'
                     '{time:1010,ispoint:190,setpoint:200},'
                     '{time:1025,ispoint:205,setpoint:200}]')
    samples = ('[{time:1000,ispoint:100,setpoint:100},'
               '{time:1010,ispoint:190,setpoint:200},'
               '{time:1025,ispoint:205,setpoint:200},'
               '{time:1035,ispoint:295,setpoint:300},'
               '{time:1050,ispoint:305,setpoint:300}]')
    first = value(js, 'clockShiftedHistorySeries(%s, 1000)' % early_samples)
    later = value(js, 'clockShiftedHistorySeries(%s, 1000)' % samples)
    assert later[:len(first)] == first
    assert [p['x'] for p in later] == [0, 10, 25, 35, 50]
    assert [p['y'] for p in later] == [100, 200, 200, 300, 300]


def test_measured_samples_continue_during_waits(js):
    samples = ('[{time:1000,ispoint:100,setpoint:100},'
               '{time:1010,ispoint:190,setpoint:200},'
               '{time:1025,ispoint:205,setpoint:200},'
               '{time:1035,ispoint:295,setpoint:300},'
               '{time:1050,ispoint:305,setpoint:300}]')
    measured = value(js, 'clockMeasuredSeries(%s, 1000)' % samples)
    assert [p['x'] for p in measured] == [0, 10, 25, 35, 50]
    assert [p['y'] for p in measured] == [100, 190, 205, 295, 305]


def test_server_timestamps_are_used_directly(js):
    profile = '[[0,100],[100,200]]'
    samples = ('[{time:1000,ispoint:100,setpoint:100},'
               '{time:1100,ispoint:200,setpoint:200}]')
    series = value(js, ('buildClockTimeSeries({profile:%s,samples:%s,'
                        'run_start_time:1000,initial_runtime:0,'
                        'latest_elapsed:100,current_runtime:100})') %
                   (profile, samples))
    assert [p['x'] for p in series['measured']] == [0, 100]
    assert [p['x'] for p in series['shifted_history']] == [0, 100]
    assert series['ideal'] == series['shifted_history']


def test_ideal_and_shifted_coincide_without_catchup(js):
    samples = ('[{time:1000,ispoint:100,setpoint:100},'
               '{time:1010,ispoint:200,setpoint:200},'
               '{time:1020,ispoint:300,setpoint:300},'
               '{time:1030,ispoint:400,setpoint:400},'
               '{time:1040,ispoint:500,setpoint:500}]')
    series = value(js, ('buildClockTimeSeries({profile:%s, samples:%s,'
                        'run_start_time:1000,initial_runtime:0,'
                        'latest_elapsed:40,current_runtime:40,'
                        '})') %
                   (PROFILE, samples))
    assert series['ideal'] == series['shifted_history']


def test_future_projection_moves_with_accumulated_delay_not_history(js):
    profile = PROFILE
    early = value(js, 'clockShiftedFutureSeries(%s, 10, 10, 1)' % profile)
    late = value(js, 'clockShiftedFutureSeries(%s, 25, 10, 1)' % profile)
    assert early[1]['x'] == 20
    assert late[1]['x'] == 35
    # Existing historical points are supplied separately and are untouched.
    history = value(js, 'clockShiftedHistorySeries([{time:1000,setpoint:100},'
                       '{time:1010,setpoint:200}], 1000)')
    assert history == [{'x': 0, 'y': 100}, {'x': 10, 'y': 200}]


def test_two_delays_shift_only_the_remaining_projection(js):
    first = value(js, ('buildClockTimeSeries({profile:%s,samples:['
                       '{time:1000,setpoint:100},{time:1010,setpoint:200},'
                       '{time:1025,setpoint:200}],run_start_time:1000,'
                       'initial_runtime:0,latest_elapsed:25,current_runtime:10})')
                  % PROFILE)
    second = value(js, ('buildClockTimeSeries({profile:%s,samples:['
                        '{time:1000,setpoint:100},{time:1010,setpoint:200},'
                        '{time:1025,setpoint:200},{time:1035,setpoint:300},'
                        '{time:1050,setpoint:300}],run_start_time:1000,'
                        'initial_runtime:0,latest_elapsed:50,current_runtime:20})')
                   % PROFILE)
    assert second['shifted_history'][:3] == first['shifted_history']
    # C was ideally due at 1020 but the first wait projects it at 1035.
    assert first['shifted_future'][1] == {'x': 35, 'y': 300}
    # The later wait does not move C's history; it moves only D onward.
    assert second['shifted_history'][3] == {'x': 35, 'y': 300}
    assert second['shifted_future'][1] == {'x': 60, 'y': 400}


def test_refresh_reconstruction_deduplicates_backlog_and_live_sample(js):
    samples = ('[{time:1000,setpoint:100,ispoint:100},'
               '{time:1010,setpoint:200,ispoint:190},'
               '{time:1010,setpoint:200,ispoint:190},'
               '{time:1025,setpoint:200,ispoint:205}]')
    series = value(js, 'buildClockTimeSeries({profile:%s,samples:%s,'
                       'run_start_time:1000,initial_runtime:0,'
                       'latest_elapsed:25,current_runtime:10})' %
                   (PROFILE, samples))
    assert len(series['measured']) == 3
    assert len(series['shifted_history']) == 3
