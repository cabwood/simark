# Retex

**Retex** is a macro-driven, literal-first language for structured writing.

Inspired by the power of TeX and LaTeX — but designed for authors, not programmers — Retex inverts the traditional paradigm. In Retex, **text is the default**. Logic, macros, and structure appear only where needed, and always in service of the writing.

There are no escape characters — only macros.  
There are no types — only values.  
There is no syntax magic — only clarity, composition, and control.

> **Retex** revisits TeX not to rebuild it — but to rediscover what authorship can be when we start with the text.

---

## ✨ Key Principles

- **Literal-first**: Unquoted text is the default. Structure and logic are opt-in.
- **Macro-native**: All behavior is extensible via first-class macros.
- **Unified object model**: Everything is a value — callable, inspectable, composable.
- **Explicit evaluation**: `\x` invokes an object. Nothing is evaluated unless you say so.
- **Stack-based scoping**: Blocks push context. Values inherit, shadow, and compose.
- **Structured blocks**: `[key = value | ...]` defines objects; `{...}` defines structure.
- **No syntax tricks**: Even `\{` is just a macro returning `{`.

---

## 💡 Why Retex?

Most tools — TeX, LaTeX, Markdown, even modern programming languages — treat text as a second-class citizen: something to escape, quote, or inject into logic.

**Retex flips the script.**  
It’s not code with embedded text — it’s **text with embedded logic**.  
It’s for humans who write, not programs that render.

---

## 📦 Examples

```retex
[title = Welcome | author = Simon]

\section[title = \title] {
  This is Retex.

  It's not escaped — it's expressed.
}


# 📘 Phases and Analogies in the Retex Language

---

## 🚦 Overview of the Phases

Retex processes documents in clearly separated phases. Each phase has distinct responsibilities, inputs, and outputs:

| Phase     | Retex Term     | Synonyms / Analogies                | Purpose                                   |
|-----------|----------------|-------------------------------------|-------------------------------------------|
| Phase 1   | Bootstrapping  | Compile-time, Macro Expansion       | Parse source into structured entities     |
| Phase 2   | Evaluation     | Runtime, Expansion, Interpretation  | Evaluate entity tree to generate output   |
| Phase 3   | Rendering      | Backend, Codegen                    | Convert structured output to final format |

---

## 🧱 Phase 1: Bootstrapping ("Compile-Time")

- **Purpose**: Parse source text using macros to build a structured `Entity` tree.
- **Reads**: `ctx.src`, `ctx.pos`, and `ctx.stack` (for fields, slots, and temporary variables).
- **Returns**: Fully structured, evaluatable objects — the document's semantic structure.
- **Analogy**: Similar to AST construction or macro expansion in a compiler.

> ✅ Entities surviving phase 1 are *self-contained* and do not access the source anymore.

---

## 🔁 Phase 2: Evaluation ("Runtime")

- **Purpose**: Walk the `Entity` tree and render or transform content.
- **Reads**: `ctx.stack` only — not `ctx.src`.
- **Mutates**: Stack for things like counters, nesting levels, and environment variables.
- **Returns**: Strings or a structured intermediate representation (e.g. JSON).

> ✅ The phase-2 context stack is fresh — it may be newly initialized with runtime-only variables.

---

## 📦 Phase 2 Output: Structured Intermediate ("p-code")

If Retex chooses to emit **JSON** or **XML** rather than direct HTML, the phase 2 output becomes a neutral, platform-independent format. This is conceptually equivalent to:

- **p-code** in compiled languages
- **IR (intermediate representation)** in modern compilers

This enables:
- Language-agnostic rendering engines
- Transformations and export pipelines
- Static analysis and tooling

---

## 🖨️ Phase 3: Rendering ("Codegen")

- **Purpose**: Convert the structured output from phase 2 (e.g. JSON) into a specific target format like HTML, PDF, etc.
- **Examples**:
  - Browser-side JavaScript rendering
  - Static site generation
  - PDF pipelines (e.g. via LaTeX or custom tools)

> 🔧 This phase can be implemented in **any language**, consuming the serialized tree from Phase 2.

---

## 💡 Design Takeaways

- Phase 2 entities must capture *all* available configuration during Phase 1.
- Phase 2 runs in a clean context — no need to retain phase-1 stack frames.
- This model makes the system:
  - Easier to test
  - Easy to serialize and cache
  - Extensible to new output formats

---

## 🧩 Entity Lifecycle by Phase

| Entity Type   | Phase | __call__() Returns | Uses `ctx.src`? | Uses `ctx.stack`? | Purpose                          |
|---------------|-------|---------------------|------------------|-------------------|----------------------------------|
| Parser Macro  | 1     | Phase 2 Entity      | ✅ Yes           | ✅ Yes            | Build structured entities        |
| Renderable    | 2     | string / JSON node  | ❌ No            | ✅ Yes            | Render or emit structure         |
| Backend Node  | 3     | HTML / PDF / etc.   | ❌ No            | ❌ Optional       | Format-specific output conversion |

---

# 🧭 Retex Language: Project Summary

## ✅ Core Architectural Decisions

### Phases

1. Phase 1 (Compilation)  
   Parses source text into Entity trees, consuming ctx.src.  
   Source is no longer needed after this phase.

2. Phase 2 (Evaluation)  
   Walks the tree using a clean ctx.stack, interpreting macros and producing structured output (e.g. JSON).

3. Phase 3 (Rendering) *(optional)*  
   Converts structured output (e.g. JSON) into HTML, PDF, etc.

### Stack Behavior

- Phase 2 uses a new context stack (not reused from parsing).
- Macros read dynamic values (like counters) from the stack.
- Entities capture all static config during Phase 1.

### Entity Behavior

- All objects are Entity instances.
- Entities must implement __call__ to support dynamic evaluation.
- Context lookups and scoping follow Python-like inheritance.

---

## 🧠 Language Design Highlights

### Textual Structure

- Sentence: ends with `|`
- Line: ends with `\n`
- Paragraph: ends with a blank line

### Context Model

- Context = stack of frames.
- Lookup searches upward through the stack.
- Each macro call pushes a frame; exiting pops it.
- Bindings (`[...]`) mutate the current frame.
- Variables are first-class objects: referenced via @name, invoked via \name.

### Evaluation Rules

- Everything is an object. Evaluation occurs only when explicitly invoked via \.
- @name references an object; \name calls it.
- `[...]` is a binding, immediately evaluated (unless wrapped).

---

## 🔁 Macro System

### Macro Definition

- Use @{...} to define anonymous macros.
- Assign with [my_macro = @{...}] to create named macros.
- Macros may include bindings, lookaheads, nested calls, and closures.

### Macro Invocation

- `[...] \macro` is the standard form (binding first).
- `\macro[...]` is allowed only if the macro is explicitly written to extract the following binding. This is opt-in, not default.

### Lookaheads

- Lookaheads inside `[...]` can extract source content that follows the binding.
- Evaluated only after the closing `]`.
- Results are injected into context prior to macro execution.

---

## 🔧 Implementation Notes

### Bindings

- parse_binding returns a Binding object.
- When ctx.flow = True, Binding is executed immediately and updates the current context.
- When wrapped (e.g. @[...]), the binding is deferred.

### Flow Control

- ctx.flow indicates whether to evaluate during parse or defer.
- Top-level context starts with flow = True.
- Macros and @{...} bodies run with flow = True.
- Inside deferred blocks, flow = False.

---

## 🔒 Locked Language Rules

1. Bindings must precede the macro that uses them.  
   The standard form is: [key=value] \macro

2. Macros may opt in to trailing binding support.  
   This enables the familiar form: \macro[key=value]  
   Internally, the macro is responsible for detecting and applying the trailing binding.  
   This is not general syntax — only macros that explicitly support this will behave this way.

---

## 🧪 Macro Usage Examples

### Header

\h Chapter 1 – The Beginning

- \h consumes the following sentence.

### Table

\table[caption=Expenses 2025]  
item | amount  
rent | 1000

- \table is defined to optionally extract and apply trailing binding before consuming rows.

### Named Macro with Lookahead Binding

[greet = @{[name = \get_sentence] hello \name}]  
\greet George | Rachel

- The macro extracts the next sentence and formats it.

---

## 🔍 Future-Safe Design Notes

- @[...], @{...}, and @[ ... ] are distinct, with well-defined behavior.
- Possible future additions:
  - @( ... ) for grouped expressions
  - @regex[...] for pattern objects
- Macros can be composed, closed over, and invoked with captured or current context — like closures.

This summary incorporates decisions made up to this point, building upon the state at the end of Discussion 2.

1. Core Philosophy:

Everything is an Entity/Macro: All constructs (static values like text/numbers, parameters, defined macros, nests, lists, errors) are represented uniformly as Entity objects in the context scope.

Unified Evaluation: Evaluation consistently occurs by looking up an Entity by name in the context and invoking its call(context) method. The complexity lies in the implementation of call() for different entity types.

2. Execution Model (\ vs. ~):

\ (Backslash) = Immediate Execution:

When encountered anywhere, \ triggers an immediate lookup of the following name in the context and calls the found entity's call() method.

The result (an Entity) replaces the \name invocation in the AST being built (if parsing a definition/default) or the output stream (if executing top-level/body).

Exception: When \parameterName is encountered during definition parsing (RHS or default value), the lookup finds a temporary ParameterPlaceholder entity whose call() method returns a Ref("parameterName") entity, effectively deferring the parameter substitution.

Read-ahead defaults (?{...}) within an immediately executed macro (\macro) operate based on the current execution context (main input stream or definition source). Using read-aheads with \ inside definitions is dangerous.

~ (Tilde) = Deferred Execution / Reference:

When encountered anywhere, ~name creates a Ref("name") entity (formerly called MacroRef) representing a deferred lookup-and-call. This Ref entity is placed in the AST.

Arguments provided (~macro<args...>) are parsed at definition time and stored within the Ref node (immediate \ calls within args are evaluated; \param references become nested Ref nodes).

The Ref.call() method performs the deferred lookup, resolves stored arguments (evaluating nested Refs), and calls the target entity's call() method.

Use Cases: Explicit deferral, creating closures/partial applications, safe use of read-ahead macros in default values (~word).

Parser/Executor Interaction: Immediate execution (\) during parsing requires tight coupling between parser and executor.

3. Syntax:

Parameter Lists (Definition): [[ name [...] = ... ]]

Uses square brackets [...].

Parameters separated by | (with optional surrounding ws).

Allowed types (reflecting named-only args in calls):

paramName (Named)

paramName ? { default_expression } (Named w/ Default)

*collectorName (e.g., *options, *kwargs, *bin)

Default expressions require {...} delimiters for unambiguous parsing.

Argument Lists (Call): \macro<...>  (Tentative decision)

Uses angle brackets <...> to distinguish from parameter lists. Requires escaping (\<) if literal < immediately follows \macroName ws?.

Arguments inside are named-only (name=value).

Arguments separated by | (with optional surrounding ws).

Order is irrelevant.

List Values (in Arguments/Defaults): {item1 | item2 | ...}

Uses curly braces {...}. Items separated by |.

Represents grouped content intended as a list.

Nest Blocks: {...} used in content for grouping/scope.

Verbatim: ...`` 

4. Parsing Strategy:

Hierarchy: Document parsed as implicit outer Nest. Content follows Nest -> Block(s) -> Line(s) -> Phrase(s) -> ExpressionUnit(s) hierarchy.

Whitespace:

Child parsers handle their own leading whitespace (parse_ws/parse_ws_nl at start).

Parent sequence parsers handle whitespace around separators (e.g., \s*\|\s*).

\nbsp parser is special: consumes surrounding whitespace (\s*\\nbsp\s*).

Whitespace collapsing (multiple spaces/tabs to one space) happens during text processing/rendering (or potentially within parse_plain), not by discarding all inter-element whitespace during structural parsing. (Introduced Whitespace nodes previously, then discussed parse_plain internal collapse - final mechanism for rendering TBD).

Separators: Parent parsers handle separators (item ( separator item )* logic). Works for zero-or-more.

Rollback: Use @rollback_on_nomatch decorator (standalone or static method @Context.rollback_on_nomatch). Ensures atomicity by restoring context.pos (and context.expected stack). If using accumulator model (which we decided against), decorator needs to handle accumulator state rollback too.

Structure: Standalone functions (parse_X(context, ...)) recommended for structural parsers. Low-level helpers (seek, eof, read_literal) remain methods of Context.

Naming: parse_X or read_X convention preferred.

5. Error Handling:

Model: Recoverable errors. Parsers return Entity on success or Error (inheriting from Group) on recoverable failure. Error contains message, pos, severity, and children (skipped/partial entities).

NoMatch: Used for clean non-matches (triggering alternatives/backtracking). Rollback ensures atomicity. Warnings generated during a NoMatch path are discarded by rollback (alternative: attach to exception).

Context Logging (@collect_errors - Discussed but Rejected): We explored but moved away from the model where parsers log errors to context.errors and a wrapper processes them, in favour of the direct Entity | Error return.

6. List Interpretation:

{...} used as a list value is parsed consistently (Block/Line/Phrase).

Macros receiving a Nest object interpret it based on expectation (list of Phrases, Lines, or Blocks).

Simple automatic collapse (single-child promotion) occurs after parsing to tidy the tree.

An explicit \list macro (formerly \collapse) is available to apply collapse rules and guarantee an enumerable list output. (User preferred implicit handling by receiver, but \list utility still seems useful).

7. Transcrypt Compatibility: Key features discussed (decorators, static methods, local classes, cache, exceptions, if s:) are expected to be compatible.