#!/usr/bin/env python

# Copyright (C) 2013-2018 Steven Myint
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Modifies strings to all use the same quote where possible."""

from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import signal
import sys
import tokenize

import untokenize


__version__ = '0.5'


try:
    unicode
except NameError:
    unicode = str


def format_code(source, preferred_quote="'"):
    """Return source code with quotes unified."""
    try:
        return _format_code(source, preferred_quote)
    except (tokenize.TokenError, IndentationError):
        return source


def _format_code(source, preferred_quote):
    """Return source code with quotes unified."""
    if not source:
        return source

    modified_tokens = []
    lines = []
    sio = io.StringIO(source)

    def readline():
        line = sio.readline()
        lines.append(line)
        return line

    # 3.12+ splits f-strings into several tokens (PEP 701)
    depth = 0
    outer_index = None
    for (token_type,
         token_string,
         start,
         end,
         line) in tokenize.generate_tokens(readline):

        if token_type in _STRING_START_TYPES:
            if depth == 0:
                outer_index = len(modified_tokens)
            depth += 1
        elif token_type in _STRING_END_TYPES:
            depth -= 1
            if depth == 0:
                literal = _source_slice(lines,
                                        modified_tokens[outer_index][2],
                                        end)
                if unify_quotes(literal, preferred_quote) != literal:
                    old = modified_tokens[outer_index]
                    modified_tokens[outer_index] = (
                        (old[0], old[1][:-1] + preferred_quote) + old[2:])
                    token_string = preferred_quote
        elif token_type == tokenize.STRING and depth == 0:
            token_string = unify_quotes(token_string,
                                        preferred_quote=preferred_quote)

        modified_tokens.append(
            (token_type, token_string, start, end, line))

    return untokenize.untokenize(modified_tokens)


_STRING_START_TYPES = tuple(
    getattr(tokenize, name) for name in ('FSTRING_START', 'TSTRING_START')
    if hasattr(tokenize, name))
_STRING_END_TYPES = tuple(
    getattr(tokenize, name) for name in ('FSTRING_END', 'TSTRING_END')
    if hasattr(tokenize, name))


def _source_slice(lines, start, end):
    """Return the source text between two (row, column) positions."""
    (start_row, start_col), (end_row, end_col) = start, end
    if start_row == end_row:
        return lines[start_row - 1][start_col:end_col]
    return (lines[start_row - 1][start_col:] +
            ''.join(lines[start_row:end_row - 1]) +
            lines[end_row - 1][:end_col])


def unify_quotes(token_string, preferred_quote):
    """Return string with quotes changed to preferred_quote if possible."""
    bad_quote = {'"': "'",
                 "'": '"'}[preferred_quote]

    allowed_starts = {
        '': bad_quote,
        'f': 'f' + bad_quote,
        'r': 'r' + bad_quote,
        'u': 'u' + bad_quote,
        'b': 'b' + bad_quote
    }

    if not any(token_string.startswith(start)
               for start in allowed_starts.values()):
        return token_string

    if token_string.count(bad_quote) != 2:
        return token_string

    if preferred_quote in token_string:
        return token_string

    assert token_string.endswith(bad_quote)
    assert len(token_string) >= 2
    for prefix, start in allowed_starts.items():
        if token_string.startswith(start):
            chars_to_strip_from_front = len(start)
            return '{prefix}{preferred_quote}{token}{preferred_quote}'.format(
                prefix=prefix,
                preferred_quote=preferred_quote,
                token=token_string[chars_to_strip_from_front:-1]
            )


def open_with_encoding(filename, encoding, mode='r'):
    """Return opened file with a specific encoding."""
    return io.open(filename, mode=mode, encoding=encoding,
                   newline='')  # Preserve line endings


def detect_encoding(filename):
    """Return file encoding."""
    try:
        with open(filename, 'rb') as input_file:
            encoding = tokenize.detect_encoding(input_file.readline)[0]

            # Check for correctness of encoding.
            with open_with_encoding(filename, encoding) as input_file:
                input_file.read()

        return encoding
    except (SyntaxError, LookupError, UnicodeDecodeError):
        return 'latin-1'


def format_file(filename, args, standard_out):
    """Run format_code() on a file.

    Returns `True` if any changes are needed and they are not being done
    in-place.

    """
    encoding = detect_encoding(filename)
    with open_with_encoding(filename, encoding=encoding) as input_file:
        source = input_file.read()
        formatted_source = format_code(
            source,
            preferred_quote=args.quote)

    if source != formatted_source:
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(formatted_source)
        else:
            import difflib
            diff = difflib.unified_diff(
                source.splitlines(),
                formatted_source.splitlines(),
                'before/' + filename,
                'after/' + filename,
                lineterm='')
            standard_out.write('\n'.join(list(diff) + ['']))

            return True

    return False


def _main(argv, standard_out, standard_error):
    """Run quotes unifying on files.

    Returns `1` if any quoting changes are still needed, otherwise
    `None`.

    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, prog='unify')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files instead of printing diffs')
    parser.add_argument('-c', '--check-only', action='store_true',
                        help='exit with a status code of 1 if any changes are'
                             ' still needed')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='drill down directories recursively')
    parser.add_argument('--quote', help='preferred quote', choices=["'", '"'],
                        default="'")
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('files', nargs='+',
                        help='files to format')

    args = parser.parse_args(argv[1:])

    filenames = list(set(args.files))
    changes_needed = False
    failure = False
    while filenames:
        name = filenames.pop(0)
        if args.recursive and os.path.isdir(name):
            for root, directories, children in os.walk(unicode(name)):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py') and
                              not f.startswith('.')]
                directories[:] = [d for d in directories
                                  if not d.startswith('.')]
        else:
            try:
                if format_file(name, args=args, standard_out=standard_out):
                    changes_needed = True
            except IOError as exception:
                print(unicode(exception), file=standard_error)
                failure = True

    if failure or (args.check_only and changes_needed):
        return 1


def main():  # pragma: no cover
    """Return exit status."""
    try:
        # Exit on broken pipe.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except AttributeError:
        # SIGPIPE is not available on Windows.
        pass

    try:
        return _main(sys.argv,
                     standard_out=sys.stdout,
                     standard_error=sys.stderr)
    except KeyboardInterrupt:
        return 2


if __name__ == '__main__':
    sys.exit(main())  # pragma: no cover
