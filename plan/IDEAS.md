# Project Ideas

## Avoid backwards-compatible shims in prototype

As we build out the prototype, we must avoid adding backwards-compatible shims
to support old versions of the code. We need to be able to iterate quickly 
and make changes to code without worrying about maintaining backwards 
compatibility. Nobody outside of this project is dependent on the code as it 
currently exists, and shims create technical debt that we have to clean up 
later anyway. When we are refactoring something, a shim is appropriate to 
confirm changes are working as expected during a test run, but they should 
be removed immediately after the test run confirms the change works as 
expected. Going back through the code and replacing calls to the old code 
with calls to the new code is critical at these moments to avoid 
accumulating technical debt for abandoned interfaces. This is not to say 
that we should break existing code: it's saying that we should go all the 
way with refactors to eradicate the old code and not leave it around with 
shims that just add to the maintenance burden. If you're going to refactor, 
finish the job while you're already in the middle of the code and have the 
context fresh to understand what needs to be changed. Don't leave it for 
later.


