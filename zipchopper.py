#!/usr/bin/python3
"""Chop up an animation ZIP archive to something Flash-drive compatible.

Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.

The [4050 Flash Drive](
https://github.com/mmcgraw74/Tektronix-4050-GPIB-Flash-Drive) is an extremely
useful device, but it seems like it may have issues handling file numbers
greater than 250 or so. (Or this could be the Tek instead.) Some ZIP files have
animations with more frames than that, so this file breaks those down into
separate zip files that have been renumbered, counting up from 1. No ZIP file
will have more than 226 files inside of it.

This program is released into the public domain without any warranty. For
details, refer to the LICENSE file distributed with this program, or, if it's
missing, to:
  - https://github.com/stepleton/hpgl2tek/blob/main/LICENSE
For further information, visit http://unlicense.org.

This program originated at https://github.com/stepleton/hpgl2tek, and may have
been modified if obtained elsewhere.

Revision history
----------------

This section records the development of this file as part of the `hpgl2tek`
project at <http://github.com/stepleton/hpgl2tek>.

22 May 2024: Initial release.
(Tom Stepleton, stepleton@gmail.com, London)
"""

import argparse
import itertools
import pathlib
import string
import re
import zipfile

from typing import Generator


def _define_flags() -> argparse.ArgumentParser:
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description=('Chop an animation ZIP file with many files in it to '
                   'separate animation ZIP files.'))

  flags.add_argument('-p', '--output_prefix',
                     help=('Prefix for output ZIP files, whose names will '
                           'have ...a.zip, ...b.zip, ...c.zip and so on '
                           'appended to them. If unspecified, the input ZIP '
                           'filename will be used instead.'), type=str)

  flags.add_argument('animation_file', help='Animation ZIP file.', type=str)

  return flags


def parse_flash_drive_filename(filename: str) -> tuple[int, str, str, int]:
  """Parse the Flash Drive's inconvenient file naming scheme.

  The 4050-series Flash Drive gadget uses an inconvenient file naming scheme
  that matches listings produced by the TLIST command but that are a bear
  to work with programmatically (best of luck doing it in a shell without
  loads of backticks). They look like this:

     11     ASCII   PROG Pi to length     3000

  The first set of digits in bytes 0-6 (left-justified, space-padded) is the
  file number. Bytes 7-14 (left-justified, space-padded) is a file type,
  usually 'ASCII', 'BINARY', or 'LAST'. (We assume it's always in all CAPS with
  no spaces inside of it.) Bytes 15-35 are a filename (left-justified,
  space-padded) that usually starts with 'PROG' (for a BASIC program) or 'DATA'
  (for data), but is blank (all spaces) for 'LAST'-type files. Byte 36 is a
  space. The final bytes (37 onward) are digits that duplicate the size of the
  file, and if I could be indulged a rant for a second, consider that if you
  wish to change a file on the Flash Drive's SD card, it's not enough to
  overwrite the file, you need to delete the old file unless your new data has
  *exactly* the same number of bytes inside of it, since it will have a
  different name! If you don't do that, consider that you will now have TWO
  files on the SD card associated with the same file number. Which one will the
  Flash Drive load on your 4050-series machine?  Murphy says: not the one you
  wanted. Hopefully you'll notice! Ask me how I know about this footgun.

  Args:
    filename: Annoying flash drive filename.

  Returns: a 4-tuple with these contents:
    [0]: The file number.
    [1]: The file type without padding spaces.
    [2]: The filename without padding spaces.
    [3]: The file size.

  Raises: ValueError if the filename doesn't adhere to this... format.
  """
  # This regex requires backtracking but we do it to give the filename a bit
  # of slack w.r.t. byte alignment. Even Monty gets that wrong sometimes.
  if (m := re.fullmatch(r'(\d+)\s+([A-Z]+)\s+(.*?)\s+(\d+)', filename)) is None:
    raise ValueError(f'Filename {filename} has sensibly abstained from '
                     'adhering to the Flash Drive filename format.')
  return int(m.group(1)), m.group(2), m.group(3), int(m.group(4))


def build_flash_drive_filename(
    number: int, type_: str, name: str, size: int) -> str:
  """Embrace complicity and build a Flash Drive filename.

  I've spoken my peace about the Flash Drive file naming scheme in the previous
  function's docstring. Here's how you can turn the information a filename
  contains into an actual filename.

  Args:
    number: The file number; must be positive.
    type_: The file type string; usually 'ASCII', 'BINARY', or 'LAST'.
    name: The name embedded in the Flash Drive file; usually starts with PROG
        or DATA.
    size: The file size; must be non-negative.

  Returns: a faint melancholy.
  """
  if number < 1 or size < 0: raise ValueError(
      'Numeric arguments to build_flash_drive_filename out of range (they '
      'should usually be positive although size can be 0 too).')
  return f'{number:<7d}{type_:<8s}{name:<21s} {size}'


def get_player_program(zf: zipfile.ZipFile) -> tuple[bytes, int]:
  """Retrieve the single animation player BASIC file from the ZIP file.

  Args:
    zf: An open ZIP file handle.

  Returns: a 2-tuple with these contents:
    [0]: Contents of the animation player BASIC file.
    [1]: File number of the animation player BASIC file.

  Raises: ValueError unless exactly one animation player BASIC file is found.
  """
  players = [n for n in zf.namelist()
             if parse_flash_drive_filename(n)[2] == 'PROG Animation player']
  if len(players) != 1: raise ValueError(
      'Failed to find exactly one animation player BASIC file in ' +
      str(zf.filename))
  player_n = players[0]
  program = zf.read(player_n)
  return program, parse_flash_drive_filename(player_n)[3]


def get_player_program_bounds(player: bytes) -> tuple[int, int]:
  """Retrieve file numbers (inclusive) of an animation's first and last frames.

  Analyses the animation player BASIC file and collects the file numbers that
  that the player will use to access drawing data for the first and last
  frames of the animation.

  Args:
    player: Contents of the animation player BASIC file, as returned by
        get_player_program. We expect this file to be the kind created by
        animate.py; if it's something else then you could get an error.

  Returns: a 2-tuple with these contents:
    [0]: File number for the data file describing the first animation frame.
    [1]: File number for the data file describing the final animation frame.
        Note that these are inclusive bounds.

  Raises: ValueError if it can't find both file numbers.
  """
  if (m := re.search(rb'\d+ LET F=(\d+)', player)) is None: raise ValueError(
      "Failed to find the first frame's file number in the player program")
  first_frame = int(m.group(1)) + 1  # see logic of the player program.

  if (m := re.search(rb'\d+ IF F>(\d+) THE', player)) is None: raise ValueError(
      "Failed to find the final frame's file number in the player program")
  final_frame = int(m.group(1))

  return first_frame, final_frame


def set_player_program_bounds(
    player: bytes,
    first_frame: int,
    final_frame: int,
) -> bytes:
  """Modify an animation player BASIC file for different first and last frames.

  Changes the first and final frame numbers in an animation player BASIC file.

  Args:
    player: Contents of the animation player BASIC file, as returned by
        get_player_program. We expect this file to be the kind created by
        animate.py; if it's something else then you could get an error.
    first_frame: File number for the data file describing the first animation
        frame (inclusive).
    final_frame: File number for the data file describing the final animation
        frame (inclusive).

  Returns: a modified animation player BASIC file.

  Raises: ValueError if it can't successfully modify the BASIC file.
  """
  replacement = bytes(rf'\1 LET F={first_frame-1}', 'UTF-8')
  player, subs = re.subn(rb'(\d+) LET F=\d+', replacement, player)
  if subs != 1: raise ValueError(
      "Failed to alter the first frame's file number in the player program")

  replacement = bytes(rf'\1 IF F>{final_frame} THE', 'UTF-8')
  player, subs = re.subn(rb'(\d+) IF F>\d+ THE', replacement, player)
  if subs != 1: raise ValueError(
      "Failed to alter the final frame's file number in the player program")

  return player


def make_chunk(zf_in: zipfile.ZipFile,
               player: bytes, first_frame: int, final_frame: int,
               zf_out: zipfile.ZipFile):
  """Excerpt an animation ZIP file into a smaller ZIP file.

  Args:
    zf_in: Input animation ZIP file.
    player: Contents of the animation player ZIP file from zf_in. You could
        load it from zf_in if you wanted, but the caller will have loaded it
        already, so why do it again.
    first_frame: (Inclusive) index of the first frame to place in the excerpt.
    final_frame: (Inclusive) index of the final frame to place in the excerpt.
    zf_out: Empty ZIP file receiving the animation excerpt.
  """
  # Derive and save altered animation player BASIC file.
  player = set_player_program_bounds(player, 2, final_frame-first_frame+2)
  zf_out.writestr(build_flash_drive_filename(
                      1, 'ASCII', 'PROG Animation Player', len(player)),
                  player)

  # Retrieve filenames from the input ZIP file.
  in_contents = zf_in.namelist()

  # Copy animation frame files (renumbered) into the output zip file.
  for f in range(first_frame, final_frame + 1):
    # Get filename of the f'th frame.
    frames = [n for n in in_contents if n.startswith(f'{f} ')]
    if len(frames) != 1: raise ValueError(
        f'Failed to find frame {f} in the animation ZIP file')
    _, type_, name, size = parse_flash_drive_filename(frames[0])

    # Compute output filename for this frame, then copy the frame data.
    new_n = build_flash_drive_filename(f-first_frame+2, type_, name, size)
    zf_out.writestr(new_n, zf_in.read(frames[0]))


def _suffix_sequence() -> Generator[str, None, None]:
  """Yields the sequence a, b, ..., z, aa, ... az, ba, ......, zz, aaa, ..."""
  for c in itertools.count(start=1):
    for chars in itertools.product(*(c * [string.ascii_lowercase])):
      yield ''.join(chars) + '.zip'


def main(FLAGS: argparse.Namespace):
  # Compute the output prefix.
  if (output_prefix := FLAGS.output_prefix) is None:
    anim_file_path = pathlib.PurePath(FLAGS.animation_file)
    output_prefix = str(anim_file_path.parent / anim_file_path.stem)

  # Open and process the input ZIP file
  with zipfile.ZipFile(FLAGS.animation_file, mode='r') as zf_in:
    # Load the player out of the ZIP file and find the file numbers of the
    # first and final frames.
    player, _ = get_player_program(zf_in)
    first_frame, final_frame = get_player_program_bounds(player)

    # The zipfiles we'll create as outputs will have this sequence of endings.
    suffixes = _suffix_sequence()

    # Portion out ZIP file into new, smaller ZIP files.
    for chunk_first_frame in range(first_frame, final_frame+1, 225):
      chunk_final_frame = min(final_frame, chunk_first_frame + 225 - 1)

      output_zip_filename = f'{output_prefix}{next(suffixes)}'
      with zipfile.ZipFile(output_zip_filename, mode='x') as zf_out:
        make_chunk(zf_in, player, chunk_first_frame, chunk_final_frame, zf_out)


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
