# Engineering Philosophy

At thirteen I taught myself Visual Basic from library books because I wanted to know how games were made. Around the same age I led a mid-size World of Warcraft guild. The leadership books I was reading said to write expectations down, so I did. The guild ran better: fewer disputes, faster decisions, less of me answering the same questions every week. Writing the rules down freed my time for actual leading.

Everything I have built since is the same move. Find the part of the work that is mechanical. Turn it into something that runs the same way every time: a script, a checklist, a written rule. Spend the saved attention on judgment.

I believe that, given enough data, anything can be modelled. Trust included. Trust works like a system too, and the one input it cannot run without is genuine human connection. You cannot fake that input and expect the system to work. No process replaces the conversation itself.

## Mechanize the scaffolding, never the core act

Every piece of work has two parts. The core act is the part that needs a person: the decision, the conversation, the design. The scaffolding is everything around the core act that holds it steady: the setup, the checks, the reminders, the structure. Mechanize the scaffolding. Leave the core act to people.

In my workshop, a jig is a guide that holds a piece of wood in position so the cut lands exactly where it should. The jig holds the work; my hand still makes the cut. The written guild rules worked the same way. They answered the repeated questions so my time went to leading. Guardrails in a codebase work the same way. They make good code the easy path, and someone still has to design the code.

In working relationships, the scaffolding is a regular meeting rhythm, showing up consistently, and checking with someone privately before raising a concern in a group. The conversation inside that structure has to be genuine. If it is not, the structure produces nothing.

Getting this wrong looks different in each direction, and I have done both. Too little mechanization: validation logic written as an instruction to an AI model instead of a script that runs the same way every time; a person re-making a decision a script settled last month. Too much mechanization: process applied where trust had to come first; a template where thinking was needed. The skill is knowing, for the piece of work in front of you, which side of the line it sits on. The line moves as tools improve. The need to know where it is does not.

## Pragmatism outranks the philosophy

Following a principle past the point where it helps is a failure of the principle. Every stance in this document comes with the same test: when following a stance makes the work harder to read, harder to change, or harder to ship, drop the stance. A rule applied without this test is a rule followed for its own sake. Any tool that enforces these stances must carry the test too.

## Every choice tells the reader something

Code is a shared language. In a shared language, every choice carries meaning. Choosing a mutable collection tells the reader the data will change; if it never changes, the immutable form was the honest choice. Marking a value read-only is a promise the compiler or type checker keeps. Leaving a function public tells the reader it has callers elsewhere, so everything starts private and becomes public only when a caller exists. Inheritance claims that one thing is a kind of another, and few designs truly have that relationship, so I build from plain data and functions instead.

What the code says must be true. A mutable collection that nothing ever changes is a small lie. Enough small lies make a codebase hard to read in a way no linter reports.

The rule holds at every scale. A module boundary is also a statement: this code does not depend on that code. If nothing enforces the statement, the codebase slowly makes it false. Import rules keep the architecture true the same way read-only markers keep the data true.

## The reader decides what is readable

Code is readable when its readers understand it, so the readers decide, and the shared style of the community outranks my private preferences when the two disagree. The readers now include machines. AI agents learned each language from millions of ordinary codebases. They see a mutable collection and expect change. They see a read-only record and expect a contract. Code that says what it means serves human readers and machine readers with no extra work.

Errors are where community style and my own principles disagree most. Exceptions are for exceptional situations, never for ordinary control flow. My own rule, that what the code says must be true, points toward returning errors as values, because a thrown exception is invisible in a function's signature. But in a language whose community throws, a codebase full of result objects reads like a foreign word: precise in the type system, unreadable to the people the style exists for. So the code throws, the way the community expects, and the honesty moves into the documentation. A function documents what it can throw, and a lint rule checks that the documentation matches the code. The rule that a function accounts for everything it does survives, written in words instead of types.

## Functional core, imperative shell

Most code should take data in and give data back. A function that takes what it needs as arguments, returns a result, and changes nothing else is cheap to test, easy to combine with other functions, and rarely has to deal with failure. The work that can fail, such as reading files, calling networks, and writing to databases, belongs at the edges of the program. This pattern has a name: a functional core, where pure functions hold the logic, inside an imperative shell, where the program touches the outside world. The purer the core, the thinner the shell.

Tests follow the shape of the code. How hard a test is to write tells you something about the code: when a test needs a page of setup and a stack of mocks, the code made that choice at writing time. Integration tests are the default for new behaviour. Unit tests get cheaper as more code takes data and returns data. Test layers are defined by where the mocks start. The boundary between core and shell is an architectural statement, so it gets enforced like one: import rules that keep file and network access out of the core.

## Owner mode and guest mode

My best code lives in repositories I own, where the vocabulary, the defaults, and the guardrails are all mine and every choice builds on the last one. In a repository someone else owns, their style governs. Breaking a local convention reads as if it means something, and that false signal costs the next reader more than my preferred style gains. Writing carefully in a house style I would never choose is the same honesty rule, applied under someone else's rules.

Changing the style of a repository I do not own is a trust problem before it is a technical problem. A better convention loses to the existing one until people trust me enough to relearn. The tools that work are teaching, and having someone respected vouch for the change.

Repositories I own carry the full standard, and they write their conventions down. A written preference stops being personal taste: a documented house style is a convention, and a convention cannot be a lie.

## Docs, defaults, guardrails

Documentation is good, defaults are better, guardrails are best. Documentation teaches the style. Defaults make the right choice the easy one. Guardrails make the wrong choice hard. How far a tool climbs these three steps predicts how much it gets used. I accept that on purpose. My personal tools ship as documentation only, because I build them for the joy of building for other engineers and for what I learn doing it, and most go unused. That is the expected result at the first step, and it says nothing bad about the work. When the organisation is the customer, the work climbs the steps until it is a default or a required check.

## Every guardrail teaches

A rule that blocks with a bare error teaches people to obey. A rule whose error message explains the reason teaches people to judge, and it keeps working when I am not in the room. The guild rules enforced behaviour and taught it at the same time, and nothing I ship should do less. No enforcement without the reason attached.

## Principles last, techniques expire

Jeff Knupp's *Idiomatic Python* shaped how I write more than any other single text, and nearly every specific technique in it has left my code. The book's lasting lesson was the principle: code is a shared language, and intent should be visible in it. Its techniques were only how that principle looked in the language of its day. The same will happen to the techniques in every language I use, so this document holds only principles. The techniques live in a separate file per language. When a technique goes stale, replace the technique and keep the principle.
