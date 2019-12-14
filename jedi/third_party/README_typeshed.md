# Typeshed in Jedi

Typeshed is used in Jedi to provide completions for all the stdlib modules.

The relevant files in jedi are in `jedi/inference/gradual`. `gradual` stands
for "gradual typing".

## Updating Typeshed

Currently Jedi has a custom implementation hosted in
https://github.com/davidhalter/typeshed.git for two reasons:

- Jedi doesn't understand Tuple.__init__ properly.
- Typeshed has a bug: https://github.com/python/typeshed/issues/2999
