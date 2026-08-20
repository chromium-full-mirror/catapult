# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import os
import shutil
import sys
import tempfile
import unittest

from unittest import mock
from pyfakefs import fake_filesystem_unittest

import py_utils
from py_utils import cloud_storage
from py_utils import lock

_CLOUD_STORAGE_GLOBAL_LOCK_PATH = os.path.join(
    os.path.dirname(__file__), 'cloud_storage_global_lock.py')


class BaseFakeFsUnitTest(fake_filesystem_unittest.TestCase):

  def setUp(self):
    self.original_environ = os.environ.copy()
    os.environ['DISABLE_CLOUD_STORAGE_IO'] = ''
    self.setUpPyfakefs()
    self.fs.CreateFile(
        os.path.join(py_utils.GetCatapultDir(),
                     'third_party', 'gsutil', 'gsutil'))

  def CreateFiles(self, file_paths):
    for f in file_paths:
      self.fs.CreateFile(f)

  def tearDown(self):
    self.tearDownPyfakefs()
    os.environ = self.original_environ

  def _FakeRunCommand(self, cmd):
    pass


class CloudStorageFakeFsUnitTest(BaseFakeFsUnitTest):

  def _AssertRunCommandRaisesError(self, communicate_strs, error):
    with mock.patch('py_utils.cloud_storage.subprocess.Popen') as popen:
      p_mock = mock.Mock()
      popen.return_value = p_mock
      p_mock.returncode = 1
      for stderr in communicate_strs:
        p_mock.communicate.return_value = ('', stderr.encode('utf-8'))
        self.assertRaises(error, cloud_storage._RunCommand, [])

  def testRunCommandCredentialsError(self):
    strs = ['You are attempting to access protected data with no configured',
            'Failure: No handler was ready to authenticate.']
    self._AssertRunCommandRaisesError(strs, cloud_storage.CredentialsError)

  def testRunCommandPermissionError(self):
    strs = ['status=403', 'status 403', '403 Forbidden']
    self._AssertRunCommandRaisesError(
      strs, cloud_storage.CloudStoragePermissionError)

  def testRunCommandNotFoundError(self):
    strs = ['InvalidUriError', 'No such object', 'No URLs matched',
            'One or more URLs matched no', 'InvalidUriError']
    self._AssertRunCommandRaisesError(strs, cloud_storage.NotFoundError)

  def testRunCommandServerError(self):
    strs = ['500 Internal Server Error']
    self._AssertRunCommandRaisesError(strs, cloud_storage.ServerError)

  def testRunCommandGenericError(self):
    strs = ['Random string']
    self._AssertRunCommandRaisesError(strs, cloud_storage.CloudStorageError)

  def testInsertCreatesValidCloudUrl(self):
    orig_run_command = cloud_storage._RunCommand
    try:
      cloud_storage._RunCommand = self._FakeRunCommand
      remote_path = 'test-remote-path.html'
      local_path = 'test-local-path.html'
      cloud_url = cloud_storage.Insert(cloud_storage.PUBLIC_BUCKET,
                                       remote_path, local_path)
      self.assertEqual('https://storage.cloud.google.com'
                       '/chromium-telemetry/test-remote-path.html',
                       cloud_url)
    finally:
      cloud_storage._RunCommand = orig_run_command

  def testUploadCreatesValidCloudUrls(self):
    orig_run_command = cloud_storage._RunCommand
    try:
      cloud_storage._RunCommand = self._FakeRunCommand
      remote_path = 'test-remote-path.html'
      local_path = 'test-local-path.html'
      cloud_filepath = cloud_storage.Upload(
          cloud_storage.PUBLIC_BUCKET, remote_path, local_path)
      self.assertEqual('https://storage.cloud.google.com'
                       '/chromium-telemetry/test-remote-path.html',
                       cloud_filepath.view_url)
      self.assertEqual('gs://chromium-telemetry/test-remote-path.html',
                       cloud_filepath.fetch_url)
    finally:
      cloud_storage._RunCommand = orig_run_command

  @mock.patch('py_utils.cloud_storage.subprocess')
  def testExistsReturnsFalse(self, subprocess_mock):
    p_mock = mock.Mock()
    subprocess_mock.Popen.return_value = p_mock
    p_mock.communicate.return_value = (
        '',
        b'CommandException: One or more URLs matched no objects.\n')
    p_mock.returncode_result = 1
    self.assertFalse(cloud_storage.Exists('fake bucket',
                                          'fake remote path'))

  @unittest.skipIf(sys.platform.startswith('win'),
                   'https://github.com/catapult-project/catapult/issues/1861')
  def testGetFilesInDirectoryIfChanged(self):
    self.CreateFiles([
        'real_dir_path/dir1/1file1.sha1',
        'real_dir_path/dir1/1file2.txt',
        'real_dir_path/dir1/1file3.sha1',
        'real_dir_path/dir2/2file.txt',
        'real_dir_path/dir3/3file1.sha1'])

    def IncrementFilesUpdated(*_):
      IncrementFilesUpdated.files_updated += 1
    IncrementFilesUpdated.files_updated = 0
    orig_get_if_changed = cloud_storage.GetIfChanged
    cloud_storage.GetIfChanged = IncrementFilesUpdated
    try:
      self.assertRaises(ValueError, cloud_storage.GetFilesInDirectoryIfChanged,
                        os.path.abspath(os.sep), cloud_storage.PUBLIC_BUCKET)
      self.assertEqual(0, IncrementFilesUpdated.files_updated)
      self.assertRaises(ValueError, cloud_storage.GetFilesInDirectoryIfChanged,
                        'fake_dir_path', cloud_storage.PUBLIC_BUCKET)
      self.assertEqual(0, IncrementFilesUpdated.files_updated)
      cloud_storage.GetFilesInDirectoryIfChanged('real_dir_path',
                                                 cloud_storage.PUBLIC_BUCKET)
      self.assertEqual(3, IncrementFilesUpdated.files_updated)
    finally:
      cloud_storage.GetIfChanged = orig_get_if_changed

  def testCopy(self):
    orig_run_command = cloud_storage._RunCommand

    def AssertCorrectRunCommandArgs(args):
      self.assertEqual(expected_args, args)
    cloud_storage._RunCommand = AssertCorrectRunCommandArgs
    expected_args = ['cp', 'gs://bucket1/remote_path1',
                     'gs://bucket2/remote_path2']
    try:
      cloud_storage.Copy('bucket1', 'bucket2', 'remote_path1', 'remote_path2')
    finally:
      cloud_storage._RunCommand = orig_run_command

  @mock.patch('py_utils.cloud_storage._RunCommand')
  def testListNoPrefix(self, mock_run_command):
    mock_run_command.return_value = '\n'.join(['gs://bucket/foo-file.txt',
                                               'gs://bucket/foo1/',
                                               'gs://bucket/foo2/'])

    self.assertEqual(cloud_storage.List('bucket'),
                     ['/foo-file.txt', '/foo1/', '/foo2/'])

  @mock.patch('py_utils.cloud_storage._RunCommand')
  def testListWithPrefix(self, mock_run_command):
    mock_run_command.return_value = '\n'.join(['gs://bucket/foo/foo-file.txt',
                                               'gs://bucket/foo/foo1/',
                                               'gs://bucket/foo/foo2/'])

    self.assertEqual(cloud_storage.List('bucket', 'foo'),
                     ['/foo/foo-file.txt', '/foo/foo1/', '/foo/foo2/'])

  @mock.patch('py_utils.cloud_storage._RunCommand')
  def testListDirs(self, mock_run_command):
    mock_run_command.return_value = '\n'.join(['gs://bucket/foo-file.txt',
                                               '',
                                               'gs://bucket/foo1/',
                                               'gs://bucket/foo2/',
                                               'gs://bucket/foo1/file.txt'])

    self.assertEqual(cloud_storage.ListDirs('bucket', 'foo*'),
                     ['/foo1/', '/foo2/'])

  @mock.patch('py_utils.cloud_storage._RunCommand')
  def testListFilesSortByName(self, mock_run_command):
    mock_run_command.return_value = '\n'.join([
        '  11  2022-01-01T16:05:16Z  gs://bucket/foo/c.txt',
        '   5  2022-03-03T16:05:16Z  gs://bucket/foo/a.txt',
        '',
        '                            gs://bucket/foo/bar/',
        '   1  2022-02-02T16:05:16Z  gs://bucket/foo/bar/b.txt',
        'TOTAL: 3 objects, 17 bytes (17 B)',
    ])

    self.assertEqual(cloud_storage.ListFiles('bucket', 'foo/*', sort_by='name'),
                     ['/foo/a.txt', '/foo/bar/b.txt', '/foo/c.txt'])

  @mock.patch('py_utils.cloud_storage._RunCommand')
  def testListFilesSortByTime(self, mock_run_command):
    mock_run_command.return_value = '\n'.join([
        '  11  2022-01-01T16:05:16Z  gs://bucket/foo/c.txt',
        '   5  2022-03-03T16:05:16Z  gs://bucket/foo/a.txt',
        '',
        '                            gs://bucket/foo/bar/',
        '   1  2022-02-02T16:05:16Z  gs://bucket/foo/bar/b.txt',
        'TOTAL: 3 objects, 17 bytes (17 B)',
    ])

    self.assertEqual(cloud_storage.ListFiles('bucket', 'foo/*', sort_by='time'),
                     ['/foo/c.txt', '/foo/bar/b.txt', '/foo/a.txt'])

  @mock.patch('py_utils.cloud_storage._RunCommand')
  def testListFilesSortBySize(self, mock_run_command):
    mock_run_command.return_value = '\n'.join([
        '  11  2022-01-01T16:05:16Z  gs://bucket/foo/c.txt',
        '   5  2022-03-03T16:05:16Z  gs://bucket/foo/a.txt',
        '',
        '                            gs://bucket/foo/bar/',
        '   1  2022-02-02T16:05:16Z  gs://bucket/foo/bar/b.txt',
        'TOTAL: 3 objects, 17 bytes (17 B)',
    ])

    self.assertEqual(cloud_storage.ListFiles('bucket', 'foo/*', sort_by='size'),
                     ['/foo/bar/b.txt', '/foo/a.txt', '/foo/c.txt'])

  @mock.patch('py_utils.cloud_storage.subprocess.Popen')
  def testSwarmingUsesExistingEnv(self, mock_popen):
    os.environ['SWARMING_HEADLESS'] = '1'

    mock_gsutil = mock_popen()
    mock_gsutil.communicate = mock.MagicMock(return_value=(b'a', b'b'))
    mock_gsutil.returncode = None

    cloud_storage.Copy('bucket1', 'bucket2', 'remote_path1', 'remote_path2')

    mock_popen.assert_called_with(
        mock.ANY, stderr=-1, env=os.environ, stdout=-1)

  @mock.patch('py_utils.cloud_storage._FileLock')
  def testDisableCloudStorageIo(self, unused_lock_mock):
    os.environ['DISABLE_CLOUD_STORAGE_IO'] = '1'
    dir_path = 'real_dir_path'
    self.fs.CreateDirectory(dir_path)
    file_path = os.path.join(dir_path, 'file1')
    file_path_sha = file_path + '.sha1'

    def CleanTimeStampFile():
      if os.path.exists(file_path + '.fetchts'):
        os.remove(file_path + '.fetchts')

    self.CreateFiles([file_path, file_path_sha])
    with open(file_path_sha, 'w') as f:
      f.write('hash1234')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.Copy('bucket1', 'bucket2', 'remote_path1', 'remote_path2')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.Get('bucket', 'foo', file_path)
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.GetIfChanged(file_path, 'foo')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.GetIfHashChanged('bar', file_path, 'bucket', 'hash1234')
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.Insert('bucket', 'foo', file_path)

    CleanTimeStampFile()
    with self.assertRaises(cloud_storage.CloudStorageIODisabled):
      cloud_storage.GetFilesInDirectoryIfChanged(dir_path, 'bucket')


@mock.patch('py_utils.cloud_storage._FileLock')
@mock.patch('py_utils.cloud_storage.ReadHash')
@mock.patch('py_utils.cloud_storage.CalculateHash')
@mock.patch('py_utils.cloud_storage._GetLocked')
class GetIfChangedTests(BaseFakeFsUnitTest):

  def testHashPathDoesNotExist(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    file_path = 'test-file-path.wpr'
    self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                cloud_storage.PUBLIC_BUCKET))
    mock_file_lock.assert_called_once_with(file_path)
    self.assertEqual(mock_get_locked.call_count, 0)
    self.assertEqual(mock_calculate_hash.call_count, 0)
    self.assertEqual(mock_read_hash.call_count, 0)

  def testHashPathExistsButFilePathDoesNot(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    mock_read_hash.return_value = 'expected_hash'
    mock_calculate_hash.return_value = 'expected_hash'
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'

    def _FakeGetLocked(bucket, expected_hash, local_path):
      del bucket, expected_hash  # unused
      self.CreateFiles([local_path])

    mock_get_locked.side_effect = _FakeGetLocked

    self.CreateFiles([hash_path])
    self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                               cloud_storage.PUBLIC_BUCKET))
    mock_file_lock.assert_called_once_with(file_path)
    mock_read_hash.assert_called_once_with(hash_path)
    mock_calculate_hash.assert_called_once_with(file_path)
    mock_get_locked.assert_called_once_with(
        cloud_storage.PUBLIC_BUCKET, 'expected_hash', file_path)

  def testHashPathAndFileHashExistWithSameHash(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    mock_read_hash.return_value = 'expected_hash'
    mock_calculate_hash.return_value = 'expected_hash'
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'

    self.CreateFiles([file_path, hash_path])
    self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                 cloud_storage.PUBLIC_BUCKET))
    mock_file_lock.assert_called_once_with(file_path)
    mock_read_hash.assert_called_once_with(hash_path)
    mock_calculate_hash.assert_called_once_with(file_path)
    self.assertEqual(mock_get_locked.call_count, 0)

  def testHashPathAndFileHashExistWithDifferentHash(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    mock_read_hash.return_value = 'expected_hash'
    mock_calculate_hash.side_effect = ['bad_hash', 'expected_hash']
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'

    def _FakeGetLocked(bucket, expected_hash, file_path):
      del bucket, expected_hash, file_path  # unused

    mock_get_locked.side_effect = _FakeGetLocked

    self.CreateFiles([file_path, hash_path])
    self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                               cloud_storage.PUBLIC_BUCKET))
    mock_file_lock.assert_called_once_with(file_path)
    mock_read_hash.assert_called_once_with(hash_path)
    self.assertEqual(mock_calculate_hash.call_count, 2)
    mock_calculate_hash.assert_has_calls([
        mock.call(file_path),
        mock.call(file_path)
    ])
    mock_get_locked.assert_called_once_with(
        cloud_storage.PUBLIC_BUCKET, 'expected_hash', file_path)

  def testNoHashComputationNeededUponSecondCall(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    mock_read_hash.return_value = 'expected_hash'
    mock_calculate_hash.side_effect = ['bad_hash', 'expected_hash']
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'

    def _FakeGetLocked(bucket, expected_hash, file_path):
      del bucket, expected_hash, file_path  # unused

    mock_get_locked.side_effect = _FakeGetLocked

    self.CreateFiles([file_path, hash_path])
    self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                               cloud_storage.PUBLIC_BUCKET))

    self.assertTrue(os.path.exists(file_path + '.fetchts'))

    self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                cloud_storage.PUBLIC_BUCKET))
    self.assertFalse(cloud_storage.GetIfChanged(file_path,
                                                cloud_storage.PUBLIC_BUCKET))
    # Subsequent invocations of GetIfChanged should not invoke CalculateHash.
    self.assertEqual(mock_calculate_hash.call_count, 2)
    self.assertEqual(mock_file_lock.call_args_list, [mock.call(file_path)] * 3)

  def testRefetchingFileUponHashFileChange(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    mock_read_hash.side_effect = ['expected_hash', 'hashNeW']
    mock_calculate_hash.side_effect = [
        'bad_hash', 'expected_hash', 'expected_hash', 'hashNeW'
    ]
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'

    def _FakeGetLocked(bucket, expected_hash, file_path):
      del bucket, expected_hash, file_path  # unused

    mock_get_locked.side_effect = _FakeGetLocked

    self.CreateFiles([file_path, hash_path])
    self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                               cloud_storage.PUBLIC_BUCKET))

    self.assertTrue(os.path.exists(file_path + '.fetchts'))

    with open(file_path + '.fetchts') as f:
      fetchts = float(f.read())

    file_obj = self.fs.GetObject(hash_path)
    file_obj.SetMTime(fetchts + 100)

    self.assertTrue(cloud_storage.GetIfChanged(file_path,
                                               cloud_storage.PUBLIC_BUCKET))
    self.assertEqual(mock_calculate_hash.call_count, 4)
    self.assertEqual(mock_file_lock.call_args_list, [mock.call(file_path)] * 2)

  def testDownloadHashMismatch(
      self, mock_get_locked, mock_calculate_hash, mock_read_hash,
      mock_file_lock):
    mock_read_hash.return_value = 'expected_hash'
    mock_calculate_hash.return_value = 'bad_hash'
    file_path = 'test-file-path.wpr'
    hash_path = file_path + '.sha1'
    self.CreateFiles([hash_path])

    def _FakeGetLocked(bucket, expected_hash, local_path):
      del bucket, expected_hash  # unused
      self.CreateFiles([local_path])

    mock_get_locked.side_effect = _FakeGetLocked

    with self.assertRaises(cloud_storage.HashMismatchError):
      cloud_storage.GetIfChanged(file_path, cloud_storage.PUBLIC_BUCKET)

    self.assertFalse(os.path.exists(file_path))
    self.assertFalse(os.path.exists(file_path + '.fetchts'))
    mock_file_lock.assert_called_once_with(file_path)
    mock_calculate_hash.assert_called_once_with(file_path)


@mock.patch('py_utils.cloud_storage._FileLock')
@mock.patch('py_utils.cloud_storage.CalculateHash')
@mock.patch('py_utils.cloud_storage._GetLocked')
class GetIfHashChangedTests(BaseFakeFsUnitTest):

  def testLocalFileExistsAndMatchesHash(
      self, mock_get_locked, mock_calculate_hash, mock_file_lock):
    mock_calculate_hash.return_value = 'expected_hash'
    file_path = 'test-file-path.wpr'
    self.CreateFiles([file_path])

    self.assertFalse(cloud_storage.GetIfHashChanged(
        'remote_path', file_path, 'bucket', 'expected_hash'))
    self.assertEqual(mock_get_locked.call_count, 0)
    mock_calculate_hash.assert_called_once_with(file_path)
    mock_file_lock.assert_called_once_with(file_path)

  def testDownloadSuccess(
      self, mock_get_locked, mock_calculate_hash, mock_file_lock):
    mock_calculate_hash.return_value = 'expected_hash'
    file_path = 'test-file-path.wpr'

    def _FakeGetLocked(bucket, cs_path, local_path):
      del bucket, cs_path  # unused
      self.CreateFiles([local_path])

    mock_get_locked.side_effect = _FakeGetLocked

    self.assertTrue(cloud_storage.GetIfHashChanged(
        'remote_path', file_path, 'bucket', 'expected_hash'))
    self.assertTrue(os.path.exists(file_path))
    self.assertEqual(mock_get_locked.call_count, 1)
    mock_calculate_hash.assert_called_once_with(file_path)
    mock_file_lock.assert_called_once_with(file_path)

  def testDownloadHashMismatch(
      self, mock_get_locked, mock_calculate_hash, mock_file_lock):
    mock_calculate_hash.return_value = 'bad_hash'
    file_path = 'test-file-path.wpr'
    fetch_ts_path = file_path + '.fetchts'
    self.CreateFiles([fetch_ts_path])

    def _FakeGetLocked(bucket, cs_path, local_path):
      del bucket, cs_path  # unused
      self.CreateFiles([local_path])

    mock_get_locked.side_effect = _FakeGetLocked

    with self.assertRaises(cloud_storage.HashMismatchError):
      cloud_storage.GetIfHashChanged(
          'remote_path', file_path, 'bucket', 'expected_hash')

    self.assertFalse(os.path.exists(file_path))
    self.assertFalse(os.path.exists(fetch_ts_path))
    self.assertEqual(mock_get_locked.call_count, 1)
    mock_calculate_hash.assert_called_once_with(file_path)
    mock_file_lock.assert_called_once_with(file_path)

  def testLocalFileExistsWithBadHashDownloadSuccess(
      self, mock_get_locked, mock_calculate_hash, mock_file_lock):
    mock_calculate_hash.side_effect = ['bad_hash', 'expected_hash']
    file_path = 'test-file-path.wpr'
    self.CreateFiles([file_path])

    def _FakeGetLocked(bucket, cs_path, local_path):
      del bucket, cs_path  # unused
      with open(local_path, 'w') as f:
        f.write('updated')

    mock_get_locked.side_effect = _FakeGetLocked

    self.assertTrue(cloud_storage.GetIfHashChanged(
        'remote_path', file_path, 'bucket', 'expected_hash'))
    self.assertEqual(mock_get_locked.call_count, 1)
    self.assertEqual(mock_calculate_hash.call_count, 2)
    mock_calculate_hash.assert_has_calls([
        mock.call(file_path),
        mock.call(file_path)
    ])
    mock_file_lock.assert_called_once_with(file_path)

  def testDownloadSuccessRemovesFetchTs(
      self, mock_get_locked, mock_calculate_hash, mock_file_lock):
    mock_calculate_hash.return_value = 'expected_hash'
    file_path = 'test-file-path.wpr'
    fetch_ts_path = file_path + '.fetchts'
    self.CreateFiles([fetch_ts_path])

    def _FakeGetLocked(bucket, cs_path, local_path):
      del bucket, cs_path  # unused
      self.CreateFiles([local_path])

    mock_get_locked.side_effect = _FakeGetLocked

    self.assertTrue(cloud_storage.GetIfHashChanged(
        'remote_path', file_path, 'bucket', 'expected_hash'))
    self.assertTrue(os.path.exists(file_path))
    self.assertFalse(os.path.exists(fetch_ts_path))
    mock_file_lock.assert_called_once_with(file_path)


class CloudStorageRealFsUnitTest(unittest.TestCase):

  def setUp(self):
    self.original_environ = os.environ.copy()
    os.environ['DISABLE_CLOUD_STORAGE_IO'] = ''

  def tearDown(self):
    os.environ = self.original_environ

  @mock.patch('py_utils.cloud_storage.LOCK_ACQUISITION_TIMEOUT', .005)
  def testGetPseudoLockUnavailableCausesTimeout(self):
    with tempfile.NamedTemporaryFile(suffix='.pseudo_lock') as pseudo_lock_fd:
      with lock.FileLock(pseudo_lock_fd, lock.LOCK_EX | lock.LOCK_NB):
        with self.assertRaises(py_utils.TimeoutException):
          file_path = pseudo_lock_fd.name.replace('.pseudo_lock', '')
          cloud_storage.GetIfChanged(file_path, cloud_storage.PUBLIC_BUCKET)

  @mock.patch('py_utils.cloud_storage.LOCK_ACQUISITION_TIMEOUT', .005)
  def testGetGlobalLockUnavailableCausesTimeout(self):
    with open(_CLOUD_STORAGE_GLOBAL_LOCK_PATH) as global_lock_fd:
      with lock.FileLock(global_lock_fd, lock.LOCK_EX | lock.LOCK_NB):
        tmp_dir = tempfile.mkdtemp()
        try:
          file_path = os.path.join(tmp_dir, 'foo')
          with self.assertRaises(py_utils.TimeoutException):
            cloud_storage.GetIfChanged(file_path, cloud_storage.PUBLIC_BUCKET)
        finally:
          shutil.rmtree(tmp_dir)


class CloudStorageErrorHandlingTest(unittest.TestCase):
  def runTest(self):
    self.assertIsInstance(cloud_storage.GetErrorObjectForCloudStorageStderr(
        'ServiceException: 401 Anonymous users does not have '
        'storage.objects.get access to object chrome-partner-telemetry'),
                          cloud_storage.CredentialsError)
    self.assertIsInstance(cloud_storage.GetErrorObjectForCloudStorageStderr(
        '403 Caller does not have storage.objects.list access to bucket '
        'chrome-telemetry'), cloud_storage.CloudStoragePermissionError)
