#!/usr/bin/env python3
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import pathlib
import shutil
import sys
import tempfile
import unittest
import zlib

from unittest import mock

try:
  from devil import devil_env  # pylint: disable=unused-import
except ModuleNotFoundError:
  sys.path.insert(1, os.path.join(os.path.dirname(__file__), '..', '..'))
  from devil import devil_env  # pylint: disable=unused-import

from devil.android import device_errors
from devil.android import devil_util



class DevilUtilHostTest(unittest.TestCase):

  def setUp(self):
    self.temp_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.temp_dir)

  def testCalculateHostHashes_singlePath(self):
    test_path = os.path.join(self.temp_dir, 'test_file.dat')
    content = b'hello world'
    pathlib.Path(test_path).write_bytes(content)

    expected_hash = hex(zlib.crc32(content) & 0xffffffff)[2:]
    out = devil_util.CalculateHostHashes([test_path])
    self.assertEqual(1, len(out))
    self.assertEqual(expected_hash, out[test_path])

  def testCalculateHostHashes_list(self):
    p1 = os.path.join(self.temp_dir, 'f1.dat')
    c1 = b'content1'
    pathlib.Path(p1).write_bytes(c1)

    p2 = os.path.join(self.temp_dir, 'f2.dat')
    c2 = b'content2'
    pathlib.Path(p2).write_bytes(c2)

    expected1 = hex(zlib.crc32(c1) & 0xffffffff)[2:]
    expected2 = hex(zlib.crc32(c2) & 0xffffffff)[2:]

    out = devil_util.CalculateHostHashes([p1, p2])
    self.assertEqual(2, len(out))
    self.assertEqual(expected1, out[p1])
    self.assertEqual(expected2, out[p2])

  def testCalculateHostHashes_withParens(self):
    test_dir = os.path.join(self.temp_dir, 'dir (dbg)')
    os.makedirs(test_dir)
    test_path = os.path.join(test_dir, 'test file.dat')
    content = b'content'
    pathlib.Path(test_path).write_bytes(content)

    expected_hash = hex(zlib.crc32(content) & 0xffffffff)[2:]
    out = devil_util.CalculateHostHashes([test_path])
    self.assertEqual(1, len(out))
    self.assertEqual(expected_hash, out[test_path])

  def testCalculateHostHashes_listWithParens(self):
    p1 = os.path.join(self.temp_dir, 'dir (dbg)', 'f 1.dat')
    os.makedirs(os.path.dirname(p1))
    c1 = b'content1'
    pathlib.Path(p1).write_bytes(c1)

    p2 = os.path.join(self.temp_dir, 'f 2 (alt).dat')
    c2 = b'content2'
    pathlib.Path(p2).write_bytes(c2)

    expected1 = hex(zlib.crc32(c1) & 0xffffffff)[2:]
    expected2 = hex(zlib.crc32(c2) & 0xffffffff)[2:]

    out = devil_util.CalculateHostHashes([p1, p2])
    self.assertEqual(2, len(out))
    self.assertEqual(expected1, out[p1])
    self.assertEqual(expected2, out[p2])

  def testCalculateHostHashes_longPathWithParens(self):
    # Force the use of response file by making combined_paths long.
    # _MAX_FILE_PATHS_LENGTH is 400.
    test_dir = os.path.join(self.temp_dir, 'dir (dbg)')
    os.makedirs(test_dir)

    paths = []
    for i in range(50):
      p = os.path.join(test_dir, f'file {i}.dat')
      pathlib.Path(p).write_text(f'content {i}')
      paths.append(p)

    out = devil_util.CalculateHostHashes(paths)
    self.assertEqual(len(paths), len(out))
    for p in paths:
      self.assertTrue(out[p])

  def testCalculateHostHashes_fileMissing(self):
    test_path = os.path.join(self.temp_dir, 'missing.dat')
    with self.assertRaises(device_errors.CommandFailedError):
      devil_util.CalculateHostHashes([test_path])

  def testCompressViaZst(self):
    dest = os.path.join(self.temp_dir, 'compressed.zst')
    devil_util.CompressViaZst(dest, 'test content\n')
    self.assertTrue(os.path.exists(dest))

  def testCreateZstCompressedArchive(self):
    src_dir = os.path.join(self.temp_dir, 'src')
    os.makedirs(src_dir)
    f1 = os.path.join(src_dir, 'file1')
    pathlib.Path(f1).write_text('content1')

    archive_path = os.path.join(self.temp_dir, 'arc.zst')
    devil_util.CreateZstCompressedArchive(archive_path, [(f1, 'file1_in_arc')])
    self.assertTrue(os.path.exists(archive_path))


class DevilUtilDeviceTest(unittest.TestCase):

  def setUp(self):
    self.mocked_attrs = {
        'devil_util_host': '/mock/path/to/devil_util_host',
        'devil_util_device': '/mock/path/to/devil_util_dist',
    }
    self._patchers = [
        mock.patch(
            'devil.devil_env._Environment.FetchPath',
            mock.Mock(side_effect=lambda a, device=None: self.mocked_attrs[a])),
        mock.patch('os.path.exists', new=mock.Mock(return_value=True)),
    ]
    for p in self._patchers:
      p.start()

  def tearDown(self):
    for p in self._patchers:
      p.stop()

  def testCalculateDeviceHashes_noPaths(self):
    device = mock.NonCallableMock()
    device.RunShellCommand = mock.Mock(side_effect=Exception())

    out = devil_util.CalculateDeviceHashes([], device)
    self.assertEqual(0, len(out))

  def testCalculateDeviceHashes_singlePath(self):
    test_paths = ['/storage/emulated/legacy/test/file.dat']

    device = mock.NonCallableMock()
    device_hash_output = [
        '0123456789abcdef',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(1, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_list(self):
    test_path = [
        '/storage/emulated/legacy/test/file0.dat',
        '/storage/emulated/legacy/test/file1.dat'
    ]
    device = mock.NonCallableMock()
    device_hash_output = [
        '0123456789abcdef',
        '123456789abcdef0',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_path, device)
      self.assertEqual(2, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file0.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file0.dat'])
      self.assertTrue('/storage/emulated/legacy/test/file1.dat' in out)
      self.assertEqual('123456789abcdef0',
                       out['/storage/emulated/legacy/test/file1.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_singlePath_linkerWarning(self):
    # See crbug/479966
    test_paths = ['/storage/emulated/legacy/test/file.dat']

    device = mock.NonCallableMock()
    device_hash_output = [
        'WARNING: linker: /data/local/tmp/devil_util/devil_util_bin: '
        'unused DT entry: type 0x1d arg 0x15db',
        'THIS_IS_NOT_A_VALID_CHECKSUM_ZZZ some random text',
        '0123456789abcdef',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(1, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_list_fileMissing(self):
    test_paths = [
        '/storage/emulated/legacy/test/file0.dat',
        '/storage/emulated/legacy/test/file1.dat'
    ]
    device = mock.NonCallableMock()
    device_hash_output = [
        '0123456789abcdef',
        '',
    ]
    device.RunShellCommand = mock.Mock(return_value=device_hash_output)

    with mock.patch('os.path.getsize', return_value=1337):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(2, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file0.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file0.dat'])
      self.assertTrue('/storage/emulated/legacy/test/file1.dat' in out)
      self.assertEqual('', out['/storage/emulated/legacy/test/file1.dat'])
      self.assertEqual(1, len(device.RunShellCommand.call_args_list))

  def testCalculateDeviceHashes_requiresBinary(self):
    test_paths = ['/storage/emulated/legacy/test/file.dat']

    device = mock.NonCallableMock()
    device.adb = mock.NonCallableMock()
    device.adb.Push = mock.Mock()
    device_hash_output = [
        'WARNING: linker: /data/local/tmp/devil_util/devil_util_bin: '
        'unused DT entry: type 0x1d arg 0x15db',
        'THIS_IS_NOT_A_VALID_CHECKSUM_ZZZ some random text',
        '0123456789abcdef',
    ]
    error = device_errors.AdbShellCommandFailedError('cmd', 'out', 2)
    device.RunShellCommand = mock.Mock(side_effect=(error, '',
                                                    device_hash_output))

    with mock.patch('os.path.isdir',
                    return_value=True), (mock.patch('os.path.getsize',
                                                    return_value=1337)):
      out = devil_util.CalculateDeviceHashes(test_paths, device)
      self.assertEqual(1, len(out))
      self.assertTrue('/storage/emulated/legacy/test/file.dat' in out)
      self.assertEqual('0123456789abcdef',
                       out['/storage/emulated/legacy/test/file.dat'])
      self.assertEqual(3, len(device.RunShellCommand.call_args_list))
      device.adb.Push.assert_called_once_with(
          '/mock/path/to/devil_util_dist/devil_util_bin',
          '/data/local/tmp/devil_util_bin')


if __name__ == '__main__':
  if os.environ.get('DEVIL_UTIL_HOST'):
    config = devil_env.LocalConfigItem('devil_util_host',
                                       devil_env.GetPlatform(),
                                       os.environ['DEVIL_UTIL_HOST'])
    config['config_type'] = 'BaseConfig'
    devil_env.config.Initialize(configs=[config])
  unittest.main(verbosity=2)
