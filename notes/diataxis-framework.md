# Implementation Standards for Technical Documentation: The Diátaxis Framework

## 1. Executive philosophy — Documentation as a function of user need

Documentation is not a secondary byproduct of the development cycle; it is a
critical interface in its own right. The term *Diátaxis* derives from the
Ancient Greek dia ("across") and taxis ("arrangement"). Strategically, our goal
is the systematic arrangement of content across the architecture of user needs.
By aligning documentation structure with the user’s specific cognitive state,
we reduce friction, foster success, and accelerate product adoption.

### The problem of "blur" and partial collapse

Traditional, feature-based documentation often fails because it ignores the
user's context. When authors "blur" the boundaries between content types —
mixing instructional steps with technical facts or background theory — the
result is structural collapse.

The most common failure is the partial collapse of Tutorials and How-to Guides.
This occurs when writers confuse the difference between "Basic/Advanced" and
the difference between "Study/Work." A tutorial is not merely *easy* documentation,
and a how-to guide is not merely *advanced.* This conflation leads to
documents that attempt to teach while the user is trying to work, or provide
exhaustive options while a student is trying to learn, frustrating both.

### The four quadrants of mastery

Standardization requires mapping every piece of content to one of four
quadrants, defined by the intersection of Action vs. Cognition and Acquisition
vs. Application.

|                    | Acquisition (Study)            | Application (Work)               |
|--------------------|-------------------------------:|---------------------------------:|
| **Action (Doing)** | Tutorials (Learning-oriented)  | How-to Guides (Goal-oriented)    |
| **Cognition (Knowing)** | Explanation (Understanding) | Reference (Information-oriented) |

## 2. Tutorials — the learning-oriented experience

A tutorial is a lesson designed to build user confidence. Its role is to
provide a guided learning experience where the author serves as a surrogate
for the absent instructor. Because the instructor is "condemned to be absent"
in written documentation, the tutorial must be perfectly reliable; the author
is responsible for the learner’s safety and success.

### Pedagogical mandates

- **Ruthlessly minimize explanation:** Do not attempt to teach by telling.
  Explanation distracts from action. Provide only the minimum necessary
  context (e.g., "We use HTTPS because it is safer") and link to in-depth
  articles for later.
- **Ignore options and alternatives:** Choices create cognitive load and
  anxiety. Decide the path for the student; diversions must be ignored to
  ensure they reach the conclusion.
- **Deliver results early and often:** Learning is the connection of cause and
  effect. Every step must produce a visible, comprehensible result to
  reaffirm the learner is on the right track.
- **Aspire to perfect reliability:** A learner who fails loses confidence in
  the tutor and the product. The tutorial must work for every user, every time.

### The language of guidance

- **Voice:** Use the first-person plural ("we").  
  Example: "In this tutorial, we will..."
- **Form:** Use direct imperatives.  
  Example: "First, do x. Now, do y."
- **Expected output:** Describe exactly what the user should see.  
  Example: "The server responds with..."
- **Orientation clues:** Use phrases like *Notice that...* to prompt observation.

## 3. How-to guides — the goal-oriented direction

How-to guides are the recipes of technical work. They provide practical
directions for an already-competent user solving a specific, real-world
problem. Their primary obligation is to help the user get work done correctly
and safely.

### Operational excellence

A high-quality how-to guide functions like a professional helper who has the
tool you were about to reach for, ready to place it in your hand.

- **Logical sequencing:** Steps must follow human activity and thinking;
  provide a sense of flow and rhythm.
- **Address real-world complexity:** Guides must be adaptable. Account for
  different starting points and provide guidance for messy realities.
- **The "action only" rule:** Assume the user knows what they want to achieve.
  Do not teach foundational skills or provide exhaustive reference data.

### Naming and language

- **Conditional imperatives:** Use "If/Then" constructions for branching
  guidance. Example: "If you want x, do y."
- **Title convention:** Use "How to [Action]" (e.g., "How to configure
  reconnection back-off policies"). Avoid ambiguous titles such as
  "Performance Monitoring."

## 4. Technical reference — the information-oriented description

Reference material is the map of the product. It provides the propositional
knowledge—the facts—required for a user to operate the machinery. It must be
austere and uncompromising to serve as a reliable platform for people who are
currently at work.

### Mapping the machinery

The architecture of reference material must mirror the architecture of the
product itself. If a method belongs to a specific class in the code, the
documentation must reflect that relationship. This consistency provides the
user with truth and certainty.

### Style and the "boring" test

- **The challenge of neutrality:** Neutral description is not a natural way of
  communicating. Authors must resist explaining or instructing in reference
  sections.
- **The boring test:** Reference material is consulted, not read. If content is
  "boring and unmemorable," it is likely functioning correctly as reference.
- **Objectivity:** Use factual statements only (e.g., "The default logging
  inherits Python's defaults"). Forbid instructional language here.

## 5. Explanation — the understanding-oriented discussion

Explanatory content answers the "So what?" of a product. It is a discursive
treatment that weaves a web of understanding, turning fragmented knowledge
into mastery.

### The "bath" test

Explanation is the only kind of documentation that makes sense to read away
from the product. It should pass the *Bath Test*: if it makes sense to read in
the bath, it belongs in the Explanation quadrant. It serves the user’s study
through reflection rather than immediate action.

### The "why" layer

Explanation opens a topic for consideration. Appropriate subjects include:

- Design decisions and justifications
- Historical context and evolution
- Technical constraints and the bigger picture
- Alternatives: weighing different approaches or opinions

Authors must resist "explanation creep." Do not include instructions or
technical descriptions within the discussion. Link to the other three
quadrants to keep the explanation bounded and pure.

## 6. The Diátaxis Compass — a tool for architectural integrity

The Compass is our truth table. Use it to clarify intentions and correct
intuitive but incorrect structural decisions.

### Decision logic

- *If* the content informs Action *and* serves Acquisition → **Tutorial**
- *If* the content informs Action *and* serves Application → **How-to Guide**
- *If* the content informs Cognition *and* serves Application → **Reference**
- *If* the content informs Cognition *and* serves Acquisition → **Explanation**

## 7. Implementation workflow — organic growth and iterative improvement

Standardization advocates for organic growth over top-down blueprint planning.
A blueprint is useless until it is finished; a seedling is complete, but never
finished. Documentation must be useful at every stage of development.

### The workflow of small steps

1. **Consider:** Look at the specific piece of content in front of you (even a
   single sentence).
2. **Assess:** Evaluate it against Diátaxis standards. Does it serve a clear
   user need? Is the language appropriate for its quadrant?
3. **Decide:** Identify one small, immediate action that would improve the
   content.
4. **Do:** Execute the change and publish it immediately. Even a single
   sentence improvement is worth committing to maintain organic growth.

### The standard of quality

We distinguish between Functional Quality (accuracy, completeness, consistency)
and Deep Quality. Functional quality is a prerequisite; the Diátaxis framework
is the catalyst for attaining Deep Quality.

### Success criteria for Deep Quality

- Anticipation: Documentation feels as if it anticipates the user's next need.
- Flow: Movement from one state to another feels right and unforced.
- Fitting human needs: Content is assessed against the human subject, not
  just the machine.
- Beauty: The overall form achieves healthy structural integrity.

Following these standards produces documentation that is logical, user-centric,
and architecturally sound—a professional interface that truly serves the
practitioner's craft.
