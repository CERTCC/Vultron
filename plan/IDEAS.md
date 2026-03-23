# Project Ideas

## Expand use of `vultron.core.models.events._mixins`

Now that we have `vultron/core/models/events/_mixins.py` with some useful  
mixins for event models and `*_id` properties, there are likely more 
concepts in the domain events that could also benefit from being rolled into 
this approach. For example, in most of the items that have an 
`ObjectIsFooMixin` (which adds the `foo_id` property based on `object_id` in 
the underlying model), there is also a `foo` property that contains richer 
data. Well, the `ObjectIsFooMixin` could also just capture the `foo` 
property as well to be consistent. In nearly all cases, we'd expect that 
once the event object lands in core we are going to want both the `foo_id` 
and the `foo` data to be available anyway, so this is almost a pre-emptive 
bug fix to ensure that we won't have any cases where `foo_id` is present but 
`foo` is missing in the future.

Secondary to this, there are also a lot of event classes that have an  
`activity: VultronActivity` field, and this could be extracted out into a 
`HasActivityMixin` that just adds the `activity` field and any related 
helper methods. 

These two mixin ideas would help us basically get to where events are mostly 
just compositions of mixins that capture common semantic patterns across the 
events.
