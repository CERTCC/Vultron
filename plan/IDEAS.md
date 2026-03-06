# Project Ideas

## Important note on ACT-1, ACT-2, and ACT-3:

At the point when we start working on actor independence, we should also 
replace the TinyDB-based implementation with a more robust MongoDB community 
edition based containerized implementation for the backend database(s). 
We're going to want to show how each actor can run their own Actor instance 
with their own database backend independently, and doing that using 
standardized mongo images and docker-compose dependencies will be a lot 
easier than continuing with TinyDB. So the work on actor independence and 
the work on the database backend replacement should be done in tandem, with 
the database work potentially preceding or coincident with the actor 
independence work.