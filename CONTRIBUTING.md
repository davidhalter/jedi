Pull Requests are great (on the **dev** branch)! Readme/Documentation changes
are ok in the master branch.

 1. Fork the Repo on github.
 2. If you are adding functionality or fixing a bug, please add a test!
 3. Add your name to AUTHORS.txt
 4. Push to your fork and submit a **pull request to the dev branch**.

My **master** branch is a 100% stable (should be). I only push to it after I am
certain that things are working out. Many people are using Jedi directly from
the github master branch.

**Please use PEP8 to style your code.**


Changing Issues to Pull Requests (Github)
-----------------------------------------

If you have have previously filed a GitHub issue and want to contribute code
that addresses that issue, we prefer it if you use
[hub](https://github.com/github/hub) to convert your existing issue to a pull
request. To do that, first push the changes to a separate branch in your fork
and then issue the following command:

    hub pull-request -b davidhalter:dev -i <issue-number> -h <your-github-username>:<your-branch-name>

It's no strict requirement though, if you don't have hub installed or prefer to
use the web interface, then feel free to post a traditional pull request.
