.. include:: ../global.rst

A little history
================

The Star Wars Jedi are awesome. My Jedi software tries to imitate a little bit
of the precognition the Jedi have. There's even an awesome `scene
<http://www.youtube.com/watch?v=5BDO3pyavOY>`_ of Monty Python Jedis :-).

But actually the name hasn't so much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *"Oh, that worries me..."*

When it's finished, I hope he'll like it :-)

I actually started Jedi, because there were no good solutions available for VIM.
Most auto-completions just didn't work well. The only good solution was PyCharm.
But I like my good old VIM. Rope was never really intended to be an
auto-completion (and also I really hate project folders for my Python scripts).
It's more of a refactoring suite. So I decided to do my own version of a
completion, which would execute non-dangerous code. But I soon realized, that
this wouldn't work. So I built an extremely recursive thing which understands
many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need quite some time, because of its recursive
nature.
