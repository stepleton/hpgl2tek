#!/usr/bin/python3
"""Create HPGL files that contain text rendered in Hershey fonts.

Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.

The Hershey fonts are free rudimentary vector fonts made by the U.S. Navy in
1967 for use with vector CRT displays. They're still useful in that
application, and they're also useful for plotters.

This program is released into the public domain without any warranty. For
details, refer to the LICENSE file distributed with this program, or, if it's
missing, to:
  - https://github.com/stepleton/hpgl2tek/blob/main/LICENSE
For further information, visit http://unlicense.org.

This program originated at https://github.com/stepleton/hpgl2tek, and may have
been modified if obtained elsewhere.

This program was written with the help of the following references:
   - https://en.wikipedia.org/wiki/HP-GL
   - http://www.batbox.org/font.html

Example usage
-------------

   ./text.py -f gothiceng -o vbs.hpgl Vegan Beef Stroganoff

yields a file called vbs.hpgl in which the phrase "Vegan Beef Stroganoff" is
rendered in fine English Gothic lettering. For further usage information,
consult the help information available via the -h flag.

Dependencies
------------

This program uses (and is mainly just a wrapper for) the HersheyFonts library
at https://github.com/apshu/HersheyFonts.

Revision history
----------------

This section records the development of this file as part of the `hpgl2tek`
project at <http://github.com/stepleton/hpgl2tek>.

22 May 2024: Initial release.
(Tom Stepleton, stepleton@gmail.com, London)
"""

import argparse
import sys

import HersheyFonts


FONT_NAMES = HersheyFonts.HersheyFonts().default_font_names


def _define_flags() -> argparse.ArgumentParser:
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description=('Generate HPGL files containing text written with the '
                   'Hershey fonts.'))

  flags.add_argument('-o', '--output',
                     help=('Destination file for the HPGL output. Leave blank '
                           'to write to standard output.'),
                     type=argparse.FileType('w'), default=sys.stdout)

  flags.add_argument('-f', '--font',
                     help=('Hershey font to use for the text. The default '
                           f'font is {FONT_NAMES[0]}.'),
                     choices=FONT_NAMES, default=FONT_NAMES[0])

  flags.add_argument('text', nargs='*', help='Text to write.', type=str)

  return flags


def render(text: str, font: str) -> str:
  """Render a text string in HPGL in the specified Hershey font."""
  if font not in FONT_NAMES: raise ValueError(
      f'{font} is not a valid Hershey font name. Valid Hershey font names are '
      f'{",".join(FONT_NAMES)}.')

  # Create and configure the HersheyFont object.
  hf = HersheyFonts.HersheyFonts()
  hf.load_default_font(font)

  # Render the text into strokes: sequences of vertices. Convert generators
  # into full lists --- we're not rendering War and Peace, we've got the RAM.
  strokes_gen = hf.strokes_for_text(text)
  strokes = [list(s) for s in strokes_gen]

  # Convert the strokes to HPGL. Note -y: the hershey fonts have the Y axis
  # pointing downward.
  hpgl = ['IN;']
  for stroke in (s for s in strokes if s):  # Skip empty strokes.
    x, y = stroke[0]
    hpgl.append(f'PU{x},{-y};')

    if len(stroke) == 1:           # Make a dot for one-point-only strokes.
      hpgl.append(f'PD{x},{-y};')  # Not sure this ever happens.
    else:
      hpgl.append('PD' + ','.join(f'{x},{-y}' for x, y in stroke[1:]) + ';')

  # Conclude the HPGL and return.
  hpgl.append('IN;\n')
  return '\n'.join(hpgl)


def main(FLAGS: argparse.Namespace):
  hpgl = render(' '.join(FLAGS.text), font=FLAGS.font)
  FLAGS.output.write(hpgl)


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
