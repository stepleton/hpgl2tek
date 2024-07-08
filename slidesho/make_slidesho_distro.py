#!/usr/bin/python3
"""Make a RC2014+Tek 4010 slideshow ZIP archive from a catalog file.

Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.

This diminuitive program prepares a ZIP file containing the files that
`slidesho.bas` needs to present a vector image slideshow to a Tektronix
4010-compatible terminal from a suitably-configured RC2014 kit computer. See
comments at the top of `slidesho.bas` for more details on how to set things up
on the RC2014 side.

To use this program, assemble a collection of vector image files full of
Tektronix 4010 terminal graphics commands (such as ones created by the
`hpgl2tek.py` program). Next, create a "catalog file" where each line contains
the filename of one of your image files, followed by one or more tabs, followed
by the name you'd like the image file to appear under in the menus that
`slidesho.bas` presents on the terminal. Finally, run this program with your
catalog file as the sole positional argument (note that there are additional
flags you may want to use --- see the flag definitions below) and the ZIP file
archive will be emitted to standard output.

This program is released into the public domain without any warranty. For
details, refer to the LICENSE file distributed with this program, or, if it's
missing, to:
  - https://github.com/stepleton/hpgl2tek/blob/main/LICENSE
For further information, visit http://unlicense.org.

This program originated at https://github.com/stepleton/hpgl2tek, and may have
been modified if obtained elsewhere.

Dependencies
------------

Python 3.10 or so is probably this program's only real dependency; 3.11
definitely works.

Revision history
----------------

This section records the development of this file as part of the `hpgl2tek`
project at <http://github.com/stepleton/hpgl2tek>.

8 July 2024: Initial release.
(Tom Stepleton, stepleton@gmail.com, London)
"""

import argparse
import dataclasses
import random
import sys
import zipfile

from collections.abc import Sequence, MutableSequence
from typing import TextIO


@dataclasses.dataclass
class ArchiveItem:
  """Slideshow archive item."""
  filename: str
  description: str
  data: bytes


def _define_flags() -> argparse.ArgumentParser:
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Make a slideshow archive .zip file from a catalog file')

  flags.add_argument('catalog_file', nargs='?',
                     help=('Catalog file naming archive contents. Leave blank '
                           'to read from standard input. Each line should '
                           'name a file to place in the archive, use one or '
                           'more tabs as a delimiter, then present a string '
                           'of text to use as the description of the file.'),
                     type=argparse.FileType('r'), default=sys.stdin)

  flags.add_argument('-o', '--output',
                     help=('Destination file for catalog archive output. '
                           'Leave blank to write to standard output.'),
                     type=argparse.FileType('wb'), default=sys.stdout.buffer)

  flags.add_argument('-s', '--shuffle',
                     help=('Shuffle the ordering of items in the catalog file '
                           'when producing the slideshow archive catalog.'),
                     action='store_true')

  return flags


def load_all_items(catalog_io: TextIO) -> MutableSequence[ArchiveItem]:
  """Load archive items listed in the catalog."""
  items: list[ArchiveItem] = []
  for line in catalog_io:
    line = line.strip()
    if not line or line.startswith('#'):  # Skip blank lines, comments.
      continue
    filename, *_, description = line.split('\t')
    with open(filename, 'rb') as f:
      data = f.read()
    items.append(ArchiveItem(filename, description, data))
  return items


def make_archive_catalog(items: Sequence[ArchiveItem]) -> bytes:
  """Create the data that goes into the catalog archive file."""
  lines: list[str] = []
  for i, item in enumerate(items):
    lines.append(f'{i:08d}.TEK')
    lines.append(f'{len(item.data)}')
    lines.append(item.description)
  lines.extend(['__END__'] * 3)  # Terminator marker
  lines.append('\r')
  return '\r'.join(lines).encode()


def main(FLAGS: argparse.Namespace):
  # Load items, make catalog.
  items = load_all_items(FLAGS.catalog_file)
  if FLAGS.shuffle: random.shuffle(items)
  # Create output archive.
  with zipfile.ZipFile(
      FLAGS.output, 'a', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    zf.writestr('CATALOG.DAT', make_archive_catalog(items))
    for i, item in enumerate(items):
      zf.writestr(f'{i:08d}.TEK', item.data)


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
