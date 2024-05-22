#!/usr/bin/python3
"""Convert HPGL files for display on some old Tektronix computers and terminals.

Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.

This program can compose multiple HPGL files into a single output file after
scaling and transforming their contents in various ways. All of this same
functionality is available to other programs when this file is used as a
module. For information on usage, see help text available with the -h flag or
docstrings.

This program is released into the public domain without any warranty. For
details, refer to the LICENSE file distributed with this program, or, if it's
missing, to:
  - https://github.com/stepleton/hpgl2tek/blob/main/LICENSE
For further information, visit http://unlicense.org.

This program originated at https://github.com/stepleton/hpgl2tek, and may have
been modified if obtained elsewhere.

Advice from Monty McGraw is gratefully acknowledged, along with help from the
following references:
   - https://en.wikipedia.org/wiki/HP-GL
   - http://www.bitsavers.org/pdf/tektronix/4006/070-1891-00_4006-1_Computer_Display_Terminal_Users_Oct_1975.pdf
   - http://www.bitsavers.org/pdf/tektronix/405x/070-2056-01_4050_ref_Jul79.pdf
   - https://github.com/mmcgraw74/Tektronix-4051-4052-4054-Program-Files/blob/master/4050R12-Graphics-Enhancement-ROM/070-4639-00_4052R12-manual-OCR.pdf

Dependencies
------------

The PIL imaging library is used to render the HPGL compositions to PNG files.

Revision history
----------------

This section records the development of this file as part of the `hpgl2tek`
project at <http://github.com/stepleton/hpgl2tek>.

22 May 2024: Initial release.
(Tom Stepleton, stepleton@gmail.com, London)
"""

import argparse
import io
import itertools
import math
import PIL.Image
import PIL.ImageDraw
import sys
import textwrap
import zipfile

from typing import Callable, Iterable, Sequence, TextIO


# Type definitions
Point = tuple[float, float]
Stroke = list[Point]
Strokes = list[Stroke]


def _define_flags() -> argparse.ArgumentParser:
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description=('Convert basic HPGL files to drawing commands for various '
                   'Tektronix storage tube-based graphical terminals and '
                   'computers.'))

  flags.add_argument('input_files', nargs='*',
                     help=('HPGL input files to convert. Leave blank to read '
                           'HPGL data from standard input.'),
                     type=argparse.FileType('r'), default=[sys.stdin])

  flags.add_argument('-o', '--output',
                     help=('Destination file for drawing command output. '
                           'Leave blank to write to standard output.'),
                     type=argparse.FileType('w'), default=sys.stdout)

  flags.add_argument('-d', '--device',
                     help=('Create drawing commands for a particular device. '
                           'tek4010 is for the Tektronix 4010 family of '
                           'terminals; tek4050r12 is for Tekronix 4050-series '
                           'computers with the R12 "fast graphics" cartridge; '
                           'tek4050r12zip creates a zip file containing an '
                           'image data file and a BASIC program to display it '
                           '(requires the -n argument); png is a PNG file.'),
                     choices=['tek4010', 'tek4050r12', 'tek4050r12zip', 'png'],
                     default='tek4010')

  flags.add_argument('-n', '--file_number',
                     help=('Output files created by --device=tek4050r12zip '
                           'are expected to be placed on a McGraw USB '
                           'Flash Drive device. Filenames should start with '
                           'this number.'), type=int)

  flags.add_argument('-t', '--transform',
                     help=('Transform specifications for input drawings. By '
                           'default, drawings are scaled to fill the entire '
                           'screen. A string of transformation commands, '
                           'separated by ! characters, changes this. Commands '
                           'include stuff like fv=flip vertical, fh=flip '
                           'horizontal, r3=rotate anticlockwise by 3 degrees, '
                           's1.1=scale by 1.1, x-2.4=displace horizontally by '
                           '-2.4, y7=displace vertically by 7. Prefix command '
                           'strings by 0: to apply to the 0th HPGL file only; '
                           'prefix by nothing to apply to all files. Separate '
                           'multiple command strings with , (comma).'),
                     type=str, default='')

  flags.add_argument('-l', '--lines',
                     help=('Extra lines to draw as individual strokes. Lines '
                           'are coded as !-separated four-point tuples: '
                           'x1!y1!x2!y2, with multiple lines separated by , '
                           '(comma). Example: '
                           '100!150!200!250,400!450!500!550. Lines are not '
                           'subject to the --transform transformation '
                           'commands.'),
                     type=str, default='')

  return flags


def hpgl_lines_to_strokes(lines: Iterable[str]) -> Strokes:
  """Convert lines of HPGL data to sequences of x,y coordinates ("strokes").

  Only PU, PD, PA, PR, AA commands are handled. Other commands are ignored.

  Args:
    lines: An iterable of lines from an HPGL file.

  Returns:
    A list of "strokes". A stroke is a sequnece of x,y coordinates that
    must all be connected by straight lines.
  """
  strokes: Strokes = list()
  curr_pos = (0., 0.)
  down_not_up = False

  for line in lines:
    new_strokes, curr_pos, down_not_up = hpgl_line_to_strokes(
        line.strip(), curr_pos, down_not_up)
    strokes.extend(new_strokes)

  return strokes


def hpgl_line_to_strokes(
    line: str, curr_pos: Point, down_not_up: bool
) -> tuple[Strokes, Point, bool]:
  """Convert one line of HPGL data to sequences of x,y coordinates ("strokes").

  Only PU, PD, PA, PR, AA commands are handled. Other commands are ignored.

  Args:
    line: A single line from an HPGL file. Can include multiple commands.
    curr_pos: Current x,y position of the plotter pen.
    down_not_up: Whether the pen is currently down.

  Returns: a tuple with two elements
    [0]: A list of "strokes". A stroke is a sequnece of x,y coordinates that
        must all be connected by straight lines.
    [1]: New current pen position.
    [2]: New pen down state.
  """

  # A simple class that accumulates strokes from sequences of x,y arguments to
  # HPGL pen commands.
  class Pen:
    strokes: Strokes
    curr_stroke: Stroke
    curr_pos: Point
    down_not_up: bool

    def __init__(self, curr_pos: Point, down_not_up: bool):
      self.strokes = list()
      self.curr_stroke = list()
      self.curr_pos = curr_pos
      self.down_not_up = down_not_up

    def flush(self):  # Save current stroke (if nonempty) and start a new one.
      if self.curr_stroke: self.strokes.append(self.curr_stroke)
      self.curr_stroke = [self.curr_pos] if self.down_not_up else list()

    def up_move(self, args: list[float]):
      self.down_not_up = False
      self.flush()
      if args: self.curr_pos = args[-2], args[-1]

    def down_move(self, args: list[float]):
      self.down_not_up = True
      if not self.curr_stroke: self.curr_stroke.append(self.curr_pos)
      self.curr_stroke.extend(zip(args[::2], args[1::2]))
      self.curr_pos = self.curr_stroke[-1]

    def either_move(self, args: list[float]):
      if self.down_not_up:
        self.down_move(args)
      else:
        self.up_move(args)

    def either_arc(self, args: list[float]):
      cx, cy, dtheta = args[:3]  # Arc centre and counter-clockwise angle.
      dtheta = dtheta * math.pi / 180.0

      # Find polar offset from arc centre.
      dx, dy = self.curr_pos[0] - cx, self.curr_pos[1] - cy
      radius = math.sqrt(dx * dx + dy * dy)
      theta = math.atan2(dy, dx)
      
      # Compute final x, y location to minimise arithmetic error.
      fx = cx + radius * math.cos(theta + dtheta)
      fy = cy + radius * math.sin(theta + dtheta)

      # For all points in between, we go step by step in 4° increments.
      steps = math.ceil(abs(dtheta * 180 / math.pi / 4))
      sdtheta = dtheta / steps
      for i in range(1, steps - 1):
        sx = cx + radius * math.cos(theta + i * sdtheta)
        sy = cy + radius * math.sin(theta + i * sdtheta)
        self.either_move([sx, sy])

      # Move to final x, y location.
      self.either_move([fx, fy])

  # Parse and draw.
  pen = Pen(curr_pos, down_not_up)
  for statement in [s.strip() for s in line.split(';') if s.strip()]:  # I know.
    op = statement[:2]
    try:
      args = [float(a.strip()) for a in statement[2:].split(',') if a.strip()]
    except ValueError:
      continue  # Skip statements with things that aren't numbers.

    match op:
      case 'PU':
        pen.up_move(args)
      case 'PD':
        pen.down_move(args)
      case 'PA':
        pen.either_move(args)
      case 'PR':
        pen.either_move(
            [sum(c) for c in zip(itertools.cycle(pen.curr_pos), args)])
      case 'AA':
        pen.either_arc(args)

  # Done parsing. Close out any stroke underway now and quit.
  pen.flush()
  return pen.strokes, pen.curr_pos, pen.down_not_up


def transform_strokes(
    strokes: Strokes,
    bl: Point = (0., 0.), tr: Point = (1000., 788.),
    # I thought the X value should be 1023, but on our 4054A, the right side
    # of the image is getting truncated.
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
    rotate: float = 0.0,
    scale: float = 1.0,
    shift_x: float = 0.0,
    shift_y: float = 0.0,
) -> Strokes:
  """Transform strokes to fill a bounding box, perhaps with other transforms.

  The resulting strokes will be centred in the bounding box, with their most
  narrowly-constrained dimension scaled to stretch across the entire box in
  that dimension. Further transforms will then be applied as directed in the
  order of the arguments below:

  Args:
    strokes: Strokes to transform. Will not be modified.
    bl: x,y coordinates of the bottom left-hand corner of the bounding box.
    tr: x,y coordinates of the top right-hand corner of the bounding box.
    flip_horizontal: Flip the drawing **along** the horizontal axis.
    flip_vertical: Flip the drawing **along** the vertical axis.
    scale: Scale the drawing by this factor around the screen midpoint.
    rotate: Rotate the drawing this many degrees anticlockwise around the
        screen midpoint.
    shift_x: Shift the drawing left or right by this amount.
    shift_y: Shift the drawing up or down by this amount.

  Returns:
    Strokes transformed as described.
  """
  # Find extreme stroke points
  min_x, min_y, max_x, max_y = 2.**31, 2.**31, -2.**31, -2.**31
  for stroke in strokes:
    for x, y in stroke:
      if x < min_x: min_x = x
      if y < min_y: min_y = y
      if x > max_x: max_x = x
      if y > max_y: max_y = y

  # Determine formulas for how to scale X and Y coordinates
  screen_dx = tr[0] - bl[0]
  screen_dy = tr[1] - bl[1]
  if screen_dx == 0. or screen_dy == 0.: raise ValueError(
    'Bounding box is degenerate: one dimension has size 0')
  stroke_dx = max_x - min_x
  stroke_dy = max_y - min_y

  # Assuming these differences are all positive:
  # screen_dx   stroke_dx    > means the image is taller than the bounding box
  # --------- ? ---------    = means they have the same proportions
  # screen_dy   stroke_dy    < means the image is wider than the bounding box
  if abs(screen_dx * stroke_dy / screen_dy) > abs(stroke_dx):
    scale_factor = screen_dy / stroke_dy
    x_shift = (screen_dx - scale_factor * stroke_dx) / 2 - scale_factor * min_x
    y_shift = bl[1] - scale_factor * min_y
  else:
    scale_factor = screen_dx / stroke_dx
    x_shift = bl[0] - scale_factor * min_x
    y_shift = (screen_dy - scale_factor * stroke_dy) / 2 - scale_factor * min_y

  # Prepare to flip along major axes.
  x_scale_factor = y_scale_factor = scale_factor
  if flip_horizontal:
    x_scale_factor = -x_scale_factor
    x_shift = tr[0] - x_shift
  if flip_vertical:
    y_scale_factor = -y_scale_factor
    y_shift = tr[1] - y_shift

  # Prepare to rotate.
  theta = rotate * math.pi / 180
  sin_theta, cos_theta = math.sin(theta), math.cos(theta)

  # First centre the strokes in the bounding box.
  xformed_strokes: Strokes = list()
  for stroke in strokes:
    xformed_strokes.append([
        (x_scale_factor * x + x_shift, y_scale_factor * y + y_shift)
        for x, y in stroke])
  strokes = xformed_strokes

  # Then apply the rotation to the strokes. Note that rotation could cause
  # some strokes to pop out of the bounding box, so you probably want to scale
  # if you're going to rotate.
  if theta != 0.0:
    mid_x, mid_y = (tr[0] - bl[0]) / 2, (tr[1] - bl[1]) / 2
    rotated_strokes: Strokes = list()
    for stroke in strokes:
      rotated_strokes.append([
          (cos_theta * (x - mid_x) - sin_theta * (y - mid_y) + mid_x,
           sin_theta * (x - mid_x) + cos_theta * (y - mid_y) + mid_y)
          for x, y in stroke])
      strokes = rotated_strokes

  # Now do even MORE stroke transformation, starting with scaling.
  if scale != 1.0:
    mid_x, mid_y = (tr[0] - bl[0]) / 2, (tr[1] - bl[1]) / 2
    scaled_strokes: Strokes = list()
    for stroke in strokes:
      scaled_strokes.append([
          (scale * (x - mid_x) + mid_x, scale * (y - mid_y) + mid_y)
          for x, y in stroke])
    strokes = scaled_strokes

  # Next translations.
  if shift_x != 0.0 or shift_y != 0.0:
    shifted_strokes: Strokes = list()
    for stroke in strokes:
      shifted_strokes.append([(x + shift_x, y + shift_y) for x, y in stroke])
    strokes = shifted_strokes

  # Round to integer and return
  rounded_strokes: Strokes = list()
  for stroke in strokes:  # 0 argument 
    rounded_strokes.append([(round(x, 0), round(y, 0)) for x, y in stroke])
  return rounded_strokes


def _convert_strokes(
    strokes: Strokes,
    point_converter: Callable[[Point, bool], list[int]],
) -> bytes:
  """Convert strokes to some kind of stream of command bytes.

  Args:
    strokes: Strokes to convert to command strings. All points in all strokes
        must be within the Tek 4010's screen area (0 < x < 1023, 0 < y < 780)
        to avoid undefined behaviour.
    point_converter: A function that converts points in strokes to sequences
        of bytes (actually lists of integers in [0, 255]) that add the point
        to the stroke. The boolean argument means that the argument point
        starts a new stroke.

  Returns:
    Some kind of stream of command bytes.
  """
  tekbytes: list[int] = list()

  # Convert all strokes into strings and accumulate.
  for stroke in strokes:
    tekbytes.extend(point_converter(stroke[0], True))
    # Draw a single dot if the stroke has only one entry in it. Otherwise,
    # draw the full stroke.
    if len(stroke) == 1:
      tekbytes.extend(point_converter(stroke[0], False))
    else:
      for xy in stroke[1:]:
        tekbytes.extend(point_converter(xy, False))

  # Return bytes as an actual string of bytes now.
  return bytes(tekbytes)


def strokes_to_tek4010(strokes: Strokes) -> bytes:
  """Convert strokes to Tek 4010 terminal line-drawing command strings.

  Args:
    strokes: Strokes to convert to command strings. All points in all strokes
        must be within the Tek 4010's screen area (0 < x < 1023, 0 < y < 780)
        to avoid undefined behaviour.

  Returns:
    Tek 4010 line-drawing command strings.
  """
  # Convert x,y coordinates to Tektronix 4010 4- or 5-byte strings (here each
  # byte is represented with an int). The move_not_draw argument indicates
  # whether the coordinate should continue a stroke drawn from a previous
  # coordinate (False) or whether it should start a new stroke at the x,y
  # location (True).
  def xy_to_4010(xy: Point, move_not_draw: bool) -> list[int]:
    x, y = round(xy[0]), round(xy[1])  # Round coordinates to ints.
    x_bits = f'{x:010b}'[-10:]  # Convert coordinates to 10-bit binary.
    y_bits = f'{y:010b}'[-10:]
    bits_1 = f'01{y_bits[:5]}'
    bits_2 = f'11{y_bits[5:]}'
    bits_3 = f'01{x_bits[:5]}'
    bits_4 = f'10{x_bits[5:]}'
    try:
      ints = [int(b, base=2) for b in (bits_1, bits_2, bits_3, bits_4)]
    except ValueError as e:
      if str(e).startswith('invalid literal'):
        raise ValueError(
            f'Final output screen coordinates out of bounds: {x=},{y=}; has '
            'something been translated, scaled, or rotated so that any part '
            'of it is positioned off screen?') from None
      raise
    return ([0x1d] + ints) if move_not_draw else ints

  return _convert_strokes(strokes, xy_to_4010) + b'\x1f'


def strokes_to_tek4050r12(strokes: Strokes) -> bytes:
  """Convert strokes to Tek 4050 R12 line-drawing command strings.

  Args:
    strokes: Strokes to convert to command strings. All points in all strokes
        must be within the Tek 4010's screen area (0 < x < 1023, 0 < y < 780)
        to avoid undefined behaviour. (Yes, 4010 area, even for the 405x.)

  Returns:
    Tek 4050 R12 line-drawing command strings.
  """
  # Convert x,y coordinates to 4050 R12 three-byte strings (here each byte is
  # represented with an int). The move_not_draw argument indicates whether the
  # coordinate should continue a stroke drawn from a previous coordinate
  # (False) or whether it should start a new stroke at the x,y location (True).
  def xy_to_4050r12(xy: Point, move_not_draw: bool) -> list[int]:
    x, y = round(xy[0]), round(xy[1])  # Round coordinates to ints.
    x_bits = f'{x:010b}'[-10:]  # Convert coordinates to 10-bit binary.
    y_bits = f'{y:010b}'[-10:]
    bits_1 = f'0{int(move_not_draw)}{x_bits[:3]}{y_bits[:3]}'
    bits_2 = f'0{x_bits[3:]}'
    bits_3 = f'0{y_bits[3:]}'
    return [int(b, base=2) for b in (bits_1, bits_2, bits_3)]

  return _convert_strokes(strokes, xy_to_4050r12)


def strokes_to_pil_image(strokes: Strokes) -> PIL.Image:
  """Convert strokes to a 1024x780 PIL image.

  Args:
    strokes: Strokes to convert to command strings. All points in all strokes
        must be within the Tek 4010's screen area (0 < x < 1023, 0 < y < 780)
        to avoid undefined behaviour. (Yes, 4010 area, even for the 405x.)

  Returns:
    A 1024x780 RGB PIL image. Only the G channel is used, because a Tek screen
    is a green screen (and because RGB == BGR when B and R are both empty).
  """
  image = PIL.Image.new('RGB', size=(1024, 780), color='black')
  draw = PIL.ImageDraw.Draw(image)
  for stroke in strokes:
    draw.line(stroke, fill=(0, 255, 0))
  return image.transpose(PIL.Image.FLIP_TOP_BOTTOM)


def strokes_to_png(strokes: Strokes) -> bytes:
  """Convert strokes to 1024x780 PNG file data.

  Args:
    strokes: Strokes to convert to command strings. All points in all strokes
        must be within the Tek 4010's screen area (0 < x < 1023, 0 < y < 780)
        to avoid undefined behaviour. (Yes, 4010 area, even for the 405x.)

  Returns:
    Binary PNG file data.
  """
  pngdata = io.BytesIO()
  strokes_to_pil_image(strokes).save(pngdata, 'PNG', optimize=True)
  return pngdata.getvalue()


def tek4050r12_to_tape_records(tektext: bytes) -> bytes:
  """Convert R12 draw command data into tape record data for the McGraw device.

  Split command data into data records no larger than 8 kilobytes, prepending a
  header to each data record, then appending a mystery final byte (nobody knows
  what it's for). Add a final record containing the length-1 string 'X' that
  tells the BASIC program to stop loading and plotting graphics data.

  Args:
    tektext: Raw R12 command bytes.

  Returns:
    Contents of a McGraw device tape records data file.
  """
  records = [tektext[p:(p+8175)] for p in range(0, len(tektext), 8175)]
  for i in range(1, len(records)):
    last = records[i - 1]
    records[i] = bytes([last[-3] | 0x40, last[-2], last[-1]]) + records[i]
  header = lambda r: bytes([0x40 | (len(r) >> 8), len(r) & 0xff])
  return b''.join(header(r) + r + b'\0' for r in records) + b'\x40\x01Xh'


def tek4050r12_to_tek4050r12zip(tektext: bytes, file_number: int) -> bytes:
  # Convert raw draw commands to Tektronix tape records.
  image = tek4050r12_to_tape_records(tektext)

  # Prepare the BASIC program to draw the graphics data.
  basic = bytes('\r'.join([
      '100 INIT',
      '110 PAGE',
     f'120 FIND@5:{file_number+1}',
      '130 DIM S$(8190)',
      '140 READ@5:S$',
      '150 IF S$="X" THEN 200',
      '160 CALL "RDRAW",S$,1,0,0',
      '170 GO TO 130',
      '200 END ', '', '']),  # Ending with space-CR-CR seems common.
      encoding='ascii')

  # Filenames for the BASIC and graphics files.
  n = file_number  # Abbreviation
  fn_basic = f'{n:<7}ASCII   PROG Draw image {n+1:<3}   {len(basic)}'
  fn_image = f'{n+1:<7}BINARY  DATA Image {n+1:<3}        {len(image)}'

  # Pack data into a zip file. We won't bother compressing.
  zipdata = io.BytesIO()
  with zipfile.ZipFile(zipdata, "a") as zf:
    zf.writestr(fn_basic, basic)
    zf.writestr(fn_image, image)
  return zipdata.getvalue()


def get_all_strokes(
    files: Sequence[TextIO],
    transforms: str,
    extra_lines: str = '',
) -> Strokes:
  """Collect (and maybe transform) all strokes from input HPGL files.

  Args:
    files: Open file handles for each of the HPGL input drawings.
    transforms: Transform specifications for the input drawings. By default,
        drawings are scaled to fill the entire screen. This string of
        transformation commands, separated by ! characters, changes this.
        Commands include stuff like fv=flip vertical, fh=flip horizontal,
        r3=rotate anticlockwise 3 degrees, s1.1=scale by 1.1, x-2.4=displace
        horizontally by -2.4, y7=displace vertically by 7. Prefix command
        strings by 0: to apply to the 0th HPGL file only; prefix by nothing to
        apply to all files. Separate multiple command strings with , (comma).
    extra_lines: Extra lines to draw as individual strokes. Lines are coded as
        !-separated four-point tuples: x1!y1!x2!y2, with multiple lines
        separated by , (comma). Example: 100!150!200!250,400!450!500!550. Lines
        are not subject to the transformation commands in transforms.

  Returns:
    Combined strokes for all of the inputs provided.
  """
  # Parse transforms into a mapping from indices into files to kwargs for
  # transform_strokes. These are kept in this dict.
  Kwargs = dict[str, bool | float]
  ts_kwargses: dict[int, Kwargs] = {}

  # It's also possible to specify "global" kwargs: kwargs that apply to all
  # of the input files. Those go in here:
  common_kwargs: Kwargs = {}

  try:
    for transform in (t.strip() for t in transforms.split(',')):
      # Parse one set of transformation commands. Look for optional frame
      # designator: if present, we're changing kwargs for the specified frame;
      # if absent, we're changing the common kwargs.
      if ':' in transform:
        index, commands = transform.split(':')
        ts_kwargs = ts_kwargses[int(index)] = dict(common_kwargs)
      else:
        commands = transform
        ts_kwargs = common_kwargs

      for command in (c.strip() for c in commands.split('!')):
        if not command:
          continue
        elif command == 'fh':
          ts_kwargs['flip_horizontal'] = True
        elif command == 'fv':
          ts_kwargs['flip_vertical'] = True
        elif command.startswith('s'):
          ts_kwargs['scale'] = float(command[1:])
        elif command.startswith('r'):
          ts_kwargs['rotate'] = float(command[1:])
        elif command.startswith('x'):
          ts_kwargs['shift_x'] = float(command[1:])
        elif command.startswith('y'):
          ts_kwargs['shift_y'] = float(command[1:])
        else:
          raise RuntimeError(f'Unrecognised transformation command "{command}"')
  except ValueError as e:
    raise RuntimeError(f'Error parsing transformations: {e}')

  # Collect and transform strokes from all input files.
  all_strokes: Strokes = []
  for i, file in enumerate(files):
    ts_kwargs = ts_kwargses.get(i, common_kwargs)
    strokes = hpgl_lines_to_strokes(file.read().splitlines())
    strokes = transform_strokes(strokes, **ts_kwargs)  # type: ignore
    all_strokes.extend(strokes)

  # Add extra lines.
  for line in (l.strip() for l in extra_lines.strip().split(',') if l):
    x1, y1, x2, y2 = (float(f) for f in line.split('!'))
    all_strokes.append([(x1, y1), (x2, y2)])

  return all_strokes


def main(FLAGS: argparse.Namespace):
  strokes = get_all_strokes(FLAGS.input_files, FLAGS.transform, FLAGS.lines)
  tektext = {'tek4010': strokes_to_tek4010,
             'tek4050r12': strokes_to_tek4050r12,
             'tek4050r12zip': strokes_to_tek4050r12,
             'png': strokes_to_png}[FLAGS.device](strokes)
  if FLAGS.device == 'tek4050r12zip':
    if FLAGS.file_number is None: raise RuntimeError(
        'The --file_number argument is required for --device=tek4050r12zip')
    tektext = tek4050r12_to_tek4050r12zip(tektext, FLAGS.file_number)
  FLAGS.output.buffer.write(tektext)


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
