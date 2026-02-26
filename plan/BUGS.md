# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## Demo Commands produce no visible output

Running from a command line, `uv run vultron-demo initialize-case` produces 
no output. This appears to be true for all of the activity pub demo commands. 
I suspect this is because those commands all have logging but no print 
statements. I am okay with the lack of print statements, but it seems like 
we need to have a way to see the logs when running the demo commands.
The default should probably be INFO level logging to the console, but should 
include a `--debug` option to switch to DEBUG level logging. We may also want
to consider adding a `--log-file` option to allow logging to a file instead of 
the console, or in addition to the console. This would be helpful for users who
want to save the logs to a file for later review, or for debugging purposes.
We should also ensure that the logging configuration is consistent across all 
demo commands, so that users have a consistent experience when running any of the
demo scripts. This could be achieved by centralizing the logging configuration in a
shared utility function or module that all demo scripts import and use to set up their
logging.