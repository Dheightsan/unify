=====
unify
=====

Modifies strings to all use the same quote where possible.


About this fork
===============

unify was written by Steven Myint and is MIT licensed, see ``LICENSE``.
The original repo is https://github.com/myint/unify. Its last release,
0.5, fails on Python 3.13 because lib2to3 was removed, and it can't be
installed on 3.14.

This fork runs on Python 3.11 to 3.14 and no longer depends on untokenize.
It also fixes f-strings on 3.12+, where 0.5 could turn ``f'{d["k"]}'`` into
``f'{d['k']}'``, which older Python can't parse. To install it::

    $ pip install git+https://github.com/Dheightsan/unify


Example
=======

After running::

    $ unify --in-place example.py

this code

.. code-block:: python

    x = "abc"
    y = 'hello'

gets formatted into this

.. code-block:: python

    x = 'abc'
    y = 'hello'
