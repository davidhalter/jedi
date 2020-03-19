.. include global.rst

History & Acknowledgements
==========================

A Little Bit of History
-----------------------

The Star Wars Jedi are awesome. My Jedi software tries to imitate a little bit
of the precognition the Jedi have. There's even an awesome `scene
<https://youtu.be/yHRJLIf7wMU>`_ of Monty Python Jedis :-).

But actually the name has not much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *"Oh, that worries me..."*

Now that it is finished, I hope he likes it :-)

I actually started Jedi back in 2012, because there were no good solutions
available for VIM.  Most auto-completions just didn't work well. The only good
solution was PyCharm.  But I like my good old VIM. Rope was never really
intended to be an auto-completion (and also I really hate project folders for
my Python scripts).  It's more of a refactoring suite. So I decided to do my
own version of a completion, which would execute non-dangerous code. But I soon
realized, that this would not work. So I started working with a lot of
recursion to to understands many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need quite some time, because of its recursive
nature.

Acknowledgements
----------------

- Takafumi Arakaki (@tkf) for creating a solid test environment and a lot of
  other things.
- Danilo Bargen (@dbrgn) for general housekeeping and being a good friend :).
- Guido van Rossum (@gvanrossum) for creating the parser generator pgen2
  (originally used in lib2to3).

.. include:: ../../AUTHORS.txt
