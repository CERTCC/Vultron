# Implementation Notes

While a complete MPCVD protocol implementation specification is out of scope for this report, we do have a few 
additional suggestions for future implementations.
In this chapter, we describe an abstract case object for use in tracking MPCVD cases.
Next, we touch on the core MPCVD protocol subprocesses (RM, EM, and CS), including how the CS model might integrate with
other processes.
Finally, we provide a few general notes on future implementations.

## General Notes

The protocol and data structures outlined in this report are intended to
facilitate interoperability among individual organizations' workflow
management systems. As such, they are focused on the exchange of
information and data necessary for the MPCVD process to function and will not likely
be sufficient to fully address any individual organization's
vulnerability response process.

