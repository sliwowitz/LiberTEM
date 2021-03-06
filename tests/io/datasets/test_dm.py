import os
import glob
import hashlib

import numpy as np
import pytest

from libertem.io.dataset.dm import DMDataSet
from libertem.udf.sum import SumUDF

from utils import dataset_correction_verification, get_testdata_path


DM_TESTDATA_PATH = os.path.join(get_testdata_path(), 'dm')
HAVE_DM_TESTDATA = os.path.exists(DM_TESTDATA_PATH)

pytestmark = pytest.mark.skipif(not HAVE_DM_TESTDATA, reason="need .dm4 testdata")  # NOQA


@pytest.fixture
def default_dm(lt_ctx):
    files = list(sorted(glob.glob(os.path.join(DM_TESTDATA_PATH, '*.dm4'))))
    ds = lt_ctx.load("dm", files=files)
    return ds


@pytest.fixture
def dm_stack_of_3d(lt_ctx):
    files = list(sorted(glob.glob(os.path.join(DM_TESTDATA_PATH, '3D', '*.dm3'))))
    ds = lt_ctx.load("dm", files=files)
    return ds


def test_simple_open(default_dm):
    assert tuple(default_dm.shape) == (10, 3838, 3710)


def test_check_valid(default_dm):
    default_dm.check_valid()


def test_read_roi(default_dm, lt_ctx):
    roi = np.zeros((10,), dtype=bool)
    roi[5] = 1
    sumj = lt_ctx.create_sum_analysis(dataset=default_dm)
    sumres = lt_ctx.run(sumj, roi=roi)
    sha1 = hashlib.sha1()
    sha1.update(sumres.intensity.raw_data)
    assert sha1.hexdigest() == "e94ed671e20ccce33d288fbcadd0f54691a29b9c"


@pytest.mark.parametrize(
    "with_roi", (True, False)
)
def test_correction(default_dm, lt_ctx, with_roi):
    ds = default_dm

    if with_roi:
        roi = np.zeros(ds.shape.nav, dtype=bool)
        roi[:1] = True
    else:
        roi = None

    dataset_correction_verification(ds=ds, roi=roi, lt_ctx=lt_ctx)


def test_detect_1(lt_ctx):
    fpath = os.path.join(DM_TESTDATA_PATH, '2018-7-17 15_29_0000.dm4')
    assert DMDataSet.detect_params(
        path=fpath,
        executor=lt_ctx.executor,
    )["parameters"] == {
        'files': [fpath],
    }


def test_detect_2(lt_ctx):
    assert DMDataSet.detect_params(
        path="nofile.someext",
        executor=lt_ctx.executor,
    ) is False


def test_same_offset(lt_ctx):
    files = glob.glob(os.path.join(DM_TESTDATA_PATH, '*.dm4'))
    ds = lt_ctx.load("dm", files=files, same_offset=True)
    ds.check_valid()


def test_repr(default_dm):
    assert repr(default_dm) == "<DMDataSet for a stack of 10 files>"


@pytest.mark.dist
def test_dm_dist(dist_ctx):
    files = dist_ctx.executor.run_function(lambda: list(sorted(glob.glob(
        os.path.join(DM_TESTDATA_PATH, "*.dm4")
    ))))
    print(files)
    ds = DMDataSet(files=files)
    ds = ds.initialize(dist_ctx.executor)
    analysis = dist_ctx.create_sum_analysis(dataset=ds)
    roi = np.random.choice([True, False], size=len(files))
    results = dist_ctx.run(analysis, roi=roi)
    assert results[0].raw_data.shape == (3838, 3710)


def test_dm_stack_fileset_offsets(dm_stack_of_3d, lt_ctx):
    fs = dm_stack_of_3d._get_fileset()
    f0, f1 = fs

    # check that the offsets in the fileset are correct:
    assert f0.num_frames == 20
    assert f1.num_frames == 20
    assert f0.start_idx == 0
    assert f0.end_idx == 20
    assert f1.start_idx == 20
    assert f1.end_idx == 40

    lt_ctx.run_udf(dataset=dm_stack_of_3d, udf=SumUDF())
