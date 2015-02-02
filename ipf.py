#! /usr/bin/env python

import struct
import sys
import os
import zlib
import argparse

SUPPORTED_FORMATS = (bytearray('\x50\x4b\x05\x06'),)

class IpfInfo(object):
    """
    This class encapsulates information about a file entry in an IPF archive.

    Attributes:
        filename: A string representing the path and name of the file.
        archivename: The name of the originating IPF archive.
        filename_length: Length of the filename.
        archivename_length: Length of the archive name.
        compressed_length: The length of the compressed file data.
        uncompressed_length: The length of the uncompressed file data.
        data_offset: Offset in the archive file where data for this file begins.
    """

    def __init__(self):
        """
        Inits IpfInfo class.
        """
        self._filename_length = 0
        self._unknown1 = None
        self._compressed_length = 0
        self._uncompressed_length = 0
        self._data_offset = 0
        self._archivename_length = 0

        self._filename = None
        self._archivename = None

    @classmethod
    def from_buffer(self, buf):
        """
        Creates IpfInfo instance from a data buffer.
        """
        info = IpfInfo()
        data = struct.unpack('<HIIIIH', buf)

        info._filename_length = data[0]
        info._crc = data[1]
        info._compressed_length = data[2]
        info._uncompressed_length = data[3]
        info._data_offset = data[4]
        info._archivename_length = data[5]
        return info

    @property
    def filename(self):
        return self._filename

    @property
    def archivename(self):
        return self._archivename

    @property
    def filename_length(self):
        return self._filename_length

    @property
    def archivename_length(self):
        return self._archivename_length

    @property
    def compressed_length(self):
        return self._compressed_length

    @property
    def uncompressed_length(self):
        return self._uncompressed_length

    @property
    def data_offset(self):
        return self._data_offset

class IpfArchive(object):
    """
    Class that represents an IPF archive file.
    """

    def __init__(self, name):
        """
        Inits IpfArchive with a file `name`.

        Note: IpfArchive will immediately try to open the file. If it does not exist, an exception will be raised.
        """
        self.name = name
        self.fullname = os.path.abspath(name)
        
        self.file_handle = open(self.name, 'rb')
        self.closed = False

        self.files = {}

        self._open()    

    def close(self):
        """
        Closes all file handles if they are not already closed.
        """
        if self.closed:
            return
        if self.file_handle:
            self.file_handle.close()
        self.closed = True

    def _open(self):
        self.file_handle.seek(-24, 2)
        self._archive_header = self.file_handle.read(24)
        self._file_size = self.file_handle.tell()

        self._archive_header_data = struct.unpack('<HIHI4sII', self._archive_header)
        self.file_count = self._archive_header_data[0]
        self._filetable_offset = self._archive_header_data[1]

        self._filefooter_offset = self._archive_header_data[3]
        self._format = self._archive_header_data[4]
        self.base_revision = self._archive_header_data[5]
        self.revision = self._archive_header_data[6]

        if self._format not in SUPPORTED_FORMATS:
            raise Exception('Unknown archive format: %s' % repr(self._format))

        # start reading file list
        self.file_handle.seek(self._filetable_offset, 0)
        for i in range(self.file_count):
            buf = self.file_handle.read(20)
            info = IpfInfo.from_buffer(buf)
            info._archivename = self.file_handle.read(info.archivename_length)
            info._filename = self.file_handle.read(info.filename_length)

            if info.filename.lower() in self.files:
                # duplicate file name?!
                raise Exception('Duplicate file name: %s' % info.filename)

            self.files[info.filename.lower()] = info

    def get(self, filename):
        """
        Retrieves the `IpfInfo` object for `filename`.

        Args:
            filename: The name of the file.

        Returns:
            An `IpfInfo` instance that describes the file entry.
            If the file could not be found, None is returned.
        """
        key = filename.lower()
        if key not in self.files:
            return None
        return self.files[key]

    def get_data(self, filename):
        """
        Returns the uncompressed data of `filename` in the archive.

        Args:
            filename: The name of the file.

        Returns:
            A string of uncompressed data.
            If the file could not be found, None is returned.
        """
        info = self.get(filename)
        if info is None:
            return None
        self.file_handle.seek(info.data_offset)
        data = self.file_handle.read(info.compressed_length)
        if info.compressed_length == info.uncompressed_length:
            return data
        return zlib.decompress(data, -15)

    def extract_all(self, output_dir):
        """
        Extracts all files into a directory.

        Args:
            output_dir: A string describing the output directory.
        """
        for filename in self.files:
            info = self.files[filename]
            output_file = os.path.join(output_dir, info.archivename, filename)
            # print output_file
            # print info.__dict__
            if os.path.isfile(output_file):
                continue
            head, tail = os.path.split(output_file)
            try:
                os.makedirs(head)
            except os.error:
                pass
            f = open(output_file, 'wb')
            try:
                f.write(self.get_data(filename))
            except:
                print('Could not unpack %s' % filename)
            f.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # functions
    parser.add_argument('-t', '--list', action='store_true', help='list the contents of an archive')
    parser.add_argument('-x', '--extract', action='store_true', help='extract files from an archive')
    parser.add_argument('-m', '--meta', action='store_true', help='show meta information of an archive')
    # options
    parser.add_argument('-f', '--file', help='use archive file')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbosely list files processed')
    parser.add_argument('-C', '--directory', metavar='DIR', help='change directory to DIR')

    args = parser.parse_args()

    if args.list and args.extract:
        parser.print_help()
        print('You can only use one function!')
    elif not any([args.list, args.extract, args.meta]):
        parser.print_help()
        print('Please specify a function!')
    else:
        if not args.file:
            parser.print_help()
            print('Please specify a file!')
        else:
            ipf = IpfArchive(args.file)

            if args.meta:
                print('{:<15}: {:}'.format('File count', ipf.file_count))
                print('{:<15}: {:}'.format('First file', ipf._filetable_offset))
                print('{:<15}: {:}'.format('Unknown', ipf._archive_header_data[2]))
                print('{:<15}: {:}'.format('Archive header', ipf._filefooter_offset))
                print('{:<15}: {:}'.format('Format', ipf._format))
                print('{:<15}: {:}'.format('Base revision', ipf.base_revision))
                print('{:<15}: {:}'.format('Revision', ipf.revision))

            if args.list:
                for k in ipf.files:
                    print('%s _ %s' % (ipf.files[k].archivename, ipf.files[k].filename))
            elif args.extract:
                ipf.extract_all(args.directory or '.')

            ipf.close()
