# Project Ideas

## Update UseCase signature

Currently, the UseCase class assumes you pass it the datalayer in the 
constructor then call `execute()` with the request. However, we actually 
want to have the constructor itself accept the request and the datalayer so 
that we can validate things before `execute()` is called. We should 
formalize a single `UseCaseRequest` type that is passed to the constructor, 
which will consolidate a lot of the individual classes in  
`vultron/core/use_cases/triggers/requests.py` allowing us to remove most or 
all of them and simplify the codebase. The Request class can have a 
lot of optional fields that are allowed to be `None`, then where some 
requests require non-optional fields they can subclass the Request class and 
adjust the field specs to make them required.  
This way, the UseCase can validate that it has the necessary parameters in 
the Request at construction time, so we can be sure that if the UseCase 
instance exists, it is valid and ready to execute.


## UseCase implementation classes should inherit from UseCase Protocol class

Classes that implement the UseCase protocol should inherit from UseCase to 
make the interface relationship clear.

## Most strings in Pydantic objects should be NonEmptyStrings

In nearly all of our Pydantic models, we have fields that are of type `str`, 
but if present they should not be empty strings. (I.e., while we want to 
allow `str | None`, we need to enforce that non-None strings are not empty. 
`vultron/wire/as2/vocab/base/types.py` already has a `NonEmptyString` type 
that we can use for this purpose, we just need to update our Pydantic models 
to use it where appropriate. We should also remove the 
`OptionalNonEmptyString` type in that file because it's redundant with  
`NonEmptyString | None`. This will help us catch bugs where empty strings 
are passed when they shouldn't be, and it will also make our data models 
more semantically clear. We should review all of our Pydantic models and 
update  string fields to use `NonEmptyString` where appropriate, ensuring  
that we maintain the same level of optionality as before (i.e., if a field  
was previously `str | None`, it should become `NonEmptyString | None`). This 
change will improve the robustness of our data validation and help prevent  
issues caused by empty string values.

## Repeated code structures in UseCases and elsewhere should be refactored into reusable components

There are a number of common patterns that we have in our UseCases, such as 
storing objects in the datalayer, retrieving objects from the datalayer, etc.

Lots of BaseModel classes is a code smell for redundancy that has not been 
squeezed out yet too: see `vultron/core/use_cases/triggers/requests.py` for 
example.

## UseCase class names should be more specific and descriptive, especially for those that handle received messages

Use case names should distinguish between those that handle messages 
received versus those that do things.  E.g., 
`RemoveEmbargoEventFromCaseReceivedUseCase` instead of  
`RemoveEmbargoEventFromCaseUseCase`