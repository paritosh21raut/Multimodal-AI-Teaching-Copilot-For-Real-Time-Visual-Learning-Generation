# MASTER PROMPT — MULTIMODAL AI TEACHING COPILOT

## 1. YOUR ROLE

You are the **Lead AI Systems Architect, Product Architect, and Technical Project Planner** for this project.

This is the FIRST session.

Your responsibility in this session is to deeply understand the product requirements, identify ambiguities, ask me the necessary questions, and then design the complete development strategy.

Do NOT start coding yet.

Do NOT create the documentation files until you have asked your important questions and I have answered them.

After I answer your questions, you will design the architecture, roadmap, specifications, development workflow, repository structure, testing strategy, and required documentation.

For future implementation sessions, your role must automatically change according to the task:

- Architecture task → Systems Architect
- Feature implementation → Senior Software Developer
- AI/ML implementation → AI/ML Engineer
- Frontend/live-display implementation → Frontend/Real-Time Systems Engineer
- Testing → QA/Test Engineer
- Performance work → Performance Engineer
- Debugging → Senior Debugging Engineer
- Security/reliability → Production/Systems Engineer

The project documentation must define this role-switching behavior so future sessions know how to operate.

---

# 2. PROJECT

Project title:

**Multimodal AI Teaching Copilot for Real-Time Visual Learning Generation**

GitHub repository:

https://github.com/paritosh21raut/Multimodal-AI-Teaching-Copilot-For-Real-Time-Visual-Learning-Generation

Current working branch:

**CLAUDE_rebuild**

All development must happen ONLY on this branch.

The repository and `.git` configuration already exist.

A Python virtual environment has already been created.

Do NOT create another repository.

Do NOT create another branch.

Do NOT modify or use another branch unless I explicitly instruct you.

The project must be developed from a **completely fresh implementation**.

---

# 3. VERY IMPORTANT — FRESH START

We have attempted this project previously.

The previous implementation is ONLY historical experience.

DO NOT:

- inspect the previous repository/code
- copy previous code
- migrate previous modules
- reproduce the previous architecture
- preserve previous folder structures
- assume previous design decisions were correct
- use previous implementation as a template

Design the new system yourself.

You may use the lessons learned from the previous attempt described below, but the implementation, architecture, filesystem, modules, interfaces, and technologies must be independently designed.

The objective is not to repair the previous system.

The objective is to build a **better system from scratch**.

---

# 4. PRODUCT VISION

The system is an AI Teaching Copilot that listens to a teacher giving a live lecture and continuously understands what is being taught.

It should understand:

- what the current topic is
- what the current subtopic is
- whether the teacher is defining something
- explaining a concept
- giving an example
- comparing things
- explaining cause/effect
- describing a process
- explaining a formula
- describing a sequence/timeline
- describing a hierarchy
- describing an application
- telling a story
- describing something that benefits from visualization
- continuing the same concept
- transitioning to a genuinely new concept

The system should then decide how the information should be represented visually.

The core system must be designed so that it can later support multiple visual-generation modes without rebuilding the entire architecture.

---

# 5. THREE FUTURE MODES

Design the core architecture so these modes can share the same underlying understanding/state system.

You should determine the final professional names for these modes.

### Mode A — Live Presentation Mode

The system listens to the lecture and generates/upgrades a live educational slide.

The slide is displayed immediately on the classroom screen.

Example:

Teacher explains the Solar System.

The system understands:

Topic → Solar System

Subtopic → Planets

Representation → Explanation

It generates an appropriate visual slide.

If the teacher starts explaining Earth's position, the system should understand that this is related to the current topic rather than blindly creating a new slide.

---

### Mode B — Live Visual Simulation / Visualization Mode

Some concepts cannot be effectively communicated through ordinary slides.

For example:

A physics teacher explains a block on a surface and forces acting on it.

Instead of merely displaying:

- Force
- Friction
- Normal reaction

the system should be capable of producing an appropriate visual representation/animation showing the block, direction of forces, movement, etc.

Other examples could include:

- physics mechanisms
- scientific processes
- mechanical motion
- electrical circuits
- wave propagation
- biological processes
- geometric transformations
- system behavior
- mathematical concepts

The system should determine when visualization is actually useful.

Do NOT assume that every concept requires animation.

---

### Mode C — Story / Video Visualization Mode

If the teacher is explaining a historical event, story, scenario, real-world process, or narrative, the system may eventually generate a short visual/video representation.

Example:

Teacher narrates a historical event.

The system could create a sequence of visual scenes that support the narration.

I am currently not certain what the technically best implementation of this mode is.

Therefore:

**Do not blindly decide to use generative video APIs.**

During architecture planning, research and determine:

- whether real-time video generation is technically practical on a local laptop
- what types of animation are feasible
- whether procedural animation is better than AI video generation
- whether SVG/canvas/WebGL/HTML animation is suitable
- whether pre-rendered assets can be combined dynamically
- how much latency is acceptable
- how much GPU/RAM is required
- whether a hybrid approach is better
- what the first realistic version of this mode should be

The final architecture should allow this mode to be added later without rebuilding the core lecture-understanding system.

---

# 6. HOW THE COMPLETE SYSTEM SHOULD WORK

The teacher starts the application.

The system performs startup/setup.

The application then waits for the teacher.

When the teacher presses **Enter**, the lecture begins.

The system starts listening.

During the lecture:

Teacher Speech
→ Speech Understanding
→ Transcript
→ Topic/Subtopic Understanding
→ Lecture Context Understanding
→ Semantic Understanding
→ Importance/Continuity Understanding
→ Representation Decision
→ Presentation/Visualization Decision
→ Content Generation
→ Live Rendering
→ Classroom Display

The exact modules and architecture are YOUR decision.

I am intentionally NOT specifying the intelligence layers or module names.

Design the architecture based on engineering requirements.

---

# 7. LIVE PRESENTATION REQUIREMENTS

The live classroom display is the most important part of the project.

The live display must:

- update quickly
- remain visually stable
- avoid unnecessary flickering
- have a professional presentation appearance
- work for a 30–60 minute lecture
- clearly show the current concept
- use proper hierarchy
- use appropriate visual representations
- avoid looking like automatically generated generic PowerPoint slides

The live display is more important than generating a `.pptx` during the lecture.

A PowerPoint file may be generated AFTER the lecture for:

- review
- sharing
- editing
- downloading
- teaching material
- lecture archive

Do NOT make PPTX generation the primary live rendering mechanism.

---

# 8. SLIDE/REPRESENTATION INTELLIGENCE

A major requirement:

**NEW CONCEPT ≠ NEW SLIDE**

The system must understand lecture continuity.

Example:

Teacher spends 5 minutes explaining "Photosynthesis".

The system must not create a new slide every time a new sentence or sub-concept appears.

It must understand:

- current topic
- current subtopic
- what is already displayed
- what new information has been added
- whether the current slide still has capacity
- whether the information requires a different representation
- whether a new slide is actually necessary

If the teacher continues explaining the same concept but the current slide becomes overloaded, the system may create another slide while maintaining conceptual continuity.

Example:

Slide 1:
Photosynthesis — Definition + Core Idea

Slide 2:
Photosynthesis — Process

Slide 3:
Photosynthesis — Factors Affecting It

This should happen based on semantic and visual requirements, not arbitrary timing.

---

# 9. GROUNDING REQUIREMENT

The teacher's lecture is the authoritative grounding source.

The system must primarily represent what the teacher is teaching.

It may add small amounts of supporting information when useful for:

- clarity
- visual explanation
- context
- readability
- connecting concepts

However, it must NOT drift outside the lecture.

Example:

Teacher is teaching Solar System to a Class 5 student.

The system must stay appropriate to the teacher's level and scope.

It must NOT suddenly introduce:

- advanced astrophysics
- unnecessary mathematical equations
- university-level concepts
- unrelated astronomy facts

The system should understand the **educational level and depth implied by the lecture**.

---

# 10. INCORRECT TEACHER STATEMENTS

The system must distinguish between:

- lecture content
- irrelevant speech
- conversational instructions
- accidental speech
- potentially incorrect statements

Example:

Teacher says:

"Everyone, take out your books."

This must NOT appear on the educational display.

Teacher says:

"Look at the screen."

This must NOT become slide content.

Teacher says something that appears factually incorrect.

The system should not blindly reproduce it as authoritative fact.

Design a mechanism for handling uncertainty/correction carefully without silently changing the teacher's intended teaching content.

The architecture should define how this works.

---

# 11. REPRESENTATION MUST MATCH MEANING

Do NOT represent everything as bullet points.

Different information should use different visual structures.

Examples:

### Definition

A definition should visually look like a definition.

Not:

- Definition
- Important point
- Meaning
- Summary

Instead, the system should create a proper definition-oriented layout.

### Explanation

Explanations can use:

- short points
- structured sections
- diagrams
- callouts
- relationships

### Comparison

Use:

- comparison tables
- two-column layouts
- visual contrast

### Process

Use:

- flow diagrams
- sequential stages
- arrows
- process cards

### Timeline

Use:

- chronological timeline

### Hierarchy

Use:

- tree structure
- nested levels

### Formula

Use:

- equation-focused layout
- variable explanations
- supporting diagram where useful

### Cause and Effect

Use:

- causal diagram
- arrows
- relationship structure

### Application

Use:

- real-world scenario
- illustration
- application flow

The system should select representations according to semantic meaning.

---

# 12. VISUAL QUALITY

Slides must look intentionally designed.

Avoid:

- generic templates
- repetitive layouts
- excessive bullet points
- random images
- unnecessary decorations
- poor typography
- overcrowding
- excessive whitespace
- inconsistent hierarchy

The system should intelligently use:

- typography
- font sizes
- emphasis
- spacing
- colors
- cards
- diagrams
- icons
- images
- visual hierarchy
- alignment
- composition

The design should feel like an actual educational presentation rather than raw AI output.

You may research modern educational presentation systems and AI presentation tools for design inspiration, but do not copy their implementation.

---

# 13. VISUAL GENERATION

The system should understand when an image is useful.

It should also understand when an image is NOT useful.

For example:

A simple definition may not require an external image.

A biological structure may benefit from an illustration.

A historical event may benefit from imagery.

A physics mechanism may require an actual diagram/animation instead of a stock image.

A process may require a flow diagram.

Design a flexible visual-generation system that can eventually support:

- retrieved images
- generated diagrams
- procedural graphics
- SVG
- charts
- flow diagrams
- timelines
- animations
- simulations
- other appropriate representations

Image retrieval is important and should be introduced relatively early in development, but choose the implementation yourself.

Everything must be free during development.

Do NOT use paid APIs.

Do NOT use Gemini API.

Find suitable free/open-source alternatives.

Paid services can be considered only as future scaling options, not for current development.

---

# 14. REFERENCE MATERIALS

Before a lecture begins, the teacher should eventually be able to provide:

- textbooks
- PDFs
- reference documents
- labeled images
- teaching material

The system should use these materials as supporting knowledge when relevant.

Example:

Teacher uploads a textbook chapter.

During the lecture, when a related concept appears, the system may use the teacher-provided material to improve the visual representation.

The architecture should keep teacher-provided reference material separate from the authoritative live transcript.

---

# 15. END-OF-LECTURE FEATURES

After the lecture, optionally generate:

- lecture notes
- concise summary
- detailed summary
- key concepts
- question bank
- quiz questions
- revision material
- generated PPTX
- lecture transcript/archive

These are post-lecture capabilities and must not interfere with the live display pipeline.

---

# 16. LONG-RUNNING SESSION

A lecture may last:

**30–60 minutes or longer.**

The architecture must therefore handle:

- long-running state
- memory management
- bounded context
- transcript accumulation
- incremental reasoning
- API limits
- latency
- failures
- recovery
- state consistency
- resource usage

Never repeatedly send the entire lecture transcript to an LLM.

Never allow context to grow indefinitely.

Avoid unnecessary model calls.

Prefer deterministic processing where appropriate.

---

# 17. PREVIOUS PROJECT — LESSONS ONLY

The previous project achieved parts of:

- microphone capture
- speech transcription
- topic detection
- AI content generation
- image retrieval
- PPT generation
- dashboard display

However, the project encountered serious problems.

Do NOT reproduce these mistakes.

Important lessons:

### Context explosion
The system accumulated too much transcript/context and repeatedly sent large context to the model.

Avoid unbounded context.

### Excessive LLM calls
Calling an LLM on every small speech segment caused unnecessary latency and API usage.

Use intelligent gating/batching.

### LLM over-control
The LLM must NOT control the entire application.

It should be a reasoning component inside a deterministic software architecture.

### Slide lifecycle problems
The system could incorrectly create slides too frequently.

Remember:

**New concept does not automatically mean new slide.**

### Dashboard coupling
The UI became too tightly coupled with processing.

The classroom display and monitoring interface must not control the core pipeline.

### Live display problems
The previous dashboard approach was not ideal for the primary classroom presentation experience.

Research and choose the appropriate live-display technology.

### PPT problems
PPT generation was treated too much like the live presentation layer.

Separate live rendering from post-lecture PPT generation.

### Poor visual representation
Not everything should become bullet points.

Representation must match meaning.

### Image retrieval problems
Random/irrelevant images reduce educational quality.

Visual retrieval must be semantically relevant.

### Long lecture reliability
The system must not degrade as lecture duration increases.

### Testing weakness
A passing unit test does NOT mean the real system works.

Always perform runtime verification.

---

# 18. TESTING PHILOSOPHY

Testing must be strict.

Do not assume:

"Tests passed → system works."

Testing must include:

- unit tests
- integration tests
- end-to-end tests
- simulated lecture tests
- long-running tests
- failure/recovery tests
- state transition tests
- latency/resource tests
- browser/live-display verification
- visual output inspection

Whenever possible:

Use one subagent to implement and another independent subagent to review/test.

Do not modify tests simply to make them pass.

If production code fails, diagnose and fix production code.

If a test is incorrect, prove why before changing it.

Do not create fake fallback outputs just to satisfy tests.

The final definition of "done" is:

**The system actually runs and produces the expected result.**

If something is only unit-tested but not runtime-verified, mark it accordingly.

---

# 19. DEVELOPMENT APPROACH

Use **spec-driven development**, but keep specifications practical and modular.

Do not create enormous documentation files that consume the entire context window.

Create only the documents that provide real engineering value.

You should decide the final documentation structure.

At minimum, consider:

- `CLAUDE.md`
- project specification
- architecture
- development roadmap
- development rules
- current state
- decisions/ADRs
- testing strategy
- feature specifications
- progress tracking

You decide the final filenames and organization.

Documentation must remain updated as implementation progresses.

---

# 20. CONTEXT MANAGEMENT

This project will be developed across multiple Claude Code sessions.

Design the documentation system specifically for this.

Do NOT require every future session to read the entire project documentation.

Create a strategy where each implementation session loads only the relevant information.

Example:

If implementing topic/lecture understanding, Claude should load:

- current state
- relevant architecture section
- relevant feature specification
- relevant interfaces/data contracts
- relevant tests

It should NOT unnecessarily load:

- video-mode specifications
- PPT implementation details
- unrelated frontend documentation
- unrelated future features

Keep documentation modular and concise.

The documentation must make it easy for a new Claude Code session to understand:

1. what the project is
2. what has already been implemented
3. what is currently being built
4. what interfaces must be preserved
5. what tests exist
6. what the next task is

---

# 21. DEVELOPMENT ROADMAP

The overall roadmap must be decided by you.

The first milestone should be an **MVP**.

### MVP

The minimum usable system should:

- listen to a live lecture
- convert speech to text
- understand the current topic/subtopic
- understand lecture continuity
- decide appropriate presentation content
- create a live educational presentation
- display it on the classroom screen

After MVP, define V1, V2, V3, etc.

The later versions should progressively introduce:

- richer representations
- image retrieval
- diagrams
- charts
- advanced visualizations
- teacher reference materials
- post-lecture materials
- live simulations
- story/video visualization
- multilingual support

You decide the optimal order based on engineering dependencies.

The architecture must be designed from the beginning so future modes do NOT require rebuilding the entire core.

---

# 22. MULTILINGUAL SUPPORT

Initial implementation:

**English only.**

Teacher speaks English.

Live display is English.

Do NOT implement multilingual functionality now unless it is required for architectural correctness.

However, design interfaces so multilingual support can be added later.

Future requirement:

Teacher may speak:

- English
- Hindi
- Marathi
- other Indian/regional languages

The teacher may also select the output language.

Examples:

English speech → English display

Hindi speech → English display

English speech → Hindi display

Mixed-language lecture → selected output language

This is a future capability.

---

# 23. HARDWARE

Current development and execution environment:

- HP Victus
- Intel i5-12500H
- NVIDIA RTX 3050
- 16 GB RAM

The system should initially work on this laptop.

Optimize intelligently for local development.

Prefer free/open-source/local solutions.

Do not assume cloud infrastructure.

---

# 24. PROJECT STARTUP EXPERIENCE

Eventually, when I run the complete system:

1. application starts
2. required components initialize
3. system shows readiness
4. system waits for the teacher
5. pressing **Enter** starts the lecture
6. live processing begins
7. classroom display starts updating

Design this interaction intentionally.

---

# 25. FREE DEVELOPMENT REQUIREMENT

For the current development:

**No paid API calls.**

**No paid tools/services.**

**Do not use Gemini API.**

Prefer:

- local models
- open-source libraries
- free APIs with reasonable limits
- deterministic algorithms
- local rendering

If a paid service would significantly improve a future production system, document it as a future optional upgrade rather than using it now.

---

# 26. ARCHITECTURAL FREEDOM

IMPORTANT:

I am intentionally NOT telling you:

- what modules to create
- what intelligence layers to create
- what framework to use
- what database to use
- what frontend framework to use
- what model to use
- what exact folder structure to use
- what exact pipeline architecture to use

You must make these decisions.

Research where appropriate.

Choose architecture based on:

- reliability
- latency
- maintainability
- extensibility
- local hardware
- free/open-source availability
- real-time requirements
- 30–60 minute lecture stability
- future visual/video modes

Do not blindly follow architectures suggested in previous discussions.

---

# 27. SUBAGENTS

Use subagents strategically when useful.

For example:

- architecture research
- technology comparison
- implementation
- independent code review
- testing
- performance analysis
- visual/UI review

When tasks are independent, parallelize them.

For critical components, prefer:

**Implementation → Independent Review → Testing → Fix → Verification**

Do not create unnecessary subagents for trivial tasks.

---

# 28. PROGRESS TRACKING

Maintain measurable project progress.

For example:

Audio/Speech — 0%
Lecture Understanding — 0%
Presentation Engine — 0%
Live Display — 0%
Visual System — 0%
Reference Materials — 0%
Post-Lecture System — 0%
Visualization Mode — 0%
Video Mode — 0%
Testing — 0%

You decide the appropriate categories.

Update the progress when meaningful milestones are completed.

Do not inflate percentages.

A component should only be considered complete when its implementation and required verification are complete.

---

# 29. GIT WORKFLOW

The repository is already connected to GitHub.

Do not repeatedly explain Git setup.

After each meaningful, verified milestone:

1. tell me briefly that a commit is recommended
2. give me the exact commands
3. give me a concise commit message
4. continue development after I confirm or commit

Avoid unnecessary commits.

Do not commit every tiny file change.

Use meaningful checkpoints.

Example:

```bash
git status
git add .
git commit -m "feat: implement live lecture state pipeline"
git push origin CLAUDE_rebuild
```

Do not make Git management the focus of development.

---

# 30. FIRST SESSION — REQUIRED BEHAVIOR

Your FIRST response must NOT create architecture documents yet.

First:

1. Analyze everything I have provided.
2. Identify ambiguities.
3. Identify technically difficult requirements.
4. Identify decisions that materially affect architecture.
5. Ask me only the questions that genuinely require my decision.
6. Group questions logically.
7. Avoid asking questions whose answer you can determine through engineering judgment/research.

Pay particular attention to:

- live display behavior
- presentation vs visualization vs video modes
- teacher interaction
- visual generation
- reference materials
- output expectations
- acceptable latency
- lecture flow
- correctness handling
- hardware limitations
- future extensibility

After I answer:

- finalize the architecture
- create the project specification
- create the roadmap
- create the architecture documentation
- create development rules
- create testing strategy
- create current-state tracking
- create decision records
- create `CLAUDE.md`
- create other necessary documents you determine are useful

Then begin implementation according to the roadmap.

---

# 31. IMPLEMENTATION SESSION BEHAVIOR

After the planning session, every implementation session should work like this:

1. Read only the necessary project documentation.
2. Inspect the current implementation.
3. Identify the exact task.
4. State a short execution plan.
5. Implement.
6. Test.
7. Run integration tests.
8. Perform runtime verification when applicable.
9. Inspect intermediate outputs.
10. Fix real failures.
11. Update relevant documentation.
12. Update progress.
13. Report what was actually completed.
14. Recommend a Git checkpoint if appropriate.
15. Move to the next clearly defined task without unnecessary discussion.

Do not spend the entire session repeatedly redesigning the architecture unless new evidence requires it.

---

# 32. COMMUNICATION STYLE

Be execution-focused.

Do not produce long motivational explanations.

Do not repeatedly explain what you are going to do.

Do not ask me to make engineering decisions that you can reasonably make yourself.

When a decision genuinely requires my product preference, ask.

Otherwise decide yourself.

During implementation, prefer concise reports:

STATUS
IMPLEMENTED
TESTED
VERIFIED
ISSUES
NEXT

The majority of your work should be actual engineering rather than conversation.

---

# 33. DEFINITION OF SUCCESS

The final product should be a robust multimodal teaching copilot capable of:

Teacher lecture
→ real-time understanding
→ topic/subtopic continuity
→ semantic interpretation
→ appropriate representation
→ visually designed live educational content
→ classroom display

and eventually:

→ interactive/animated visualization

and eventually:

→ story/video visualization

while maintaining a shared core understanding system.

The architecture must be extensible enough that adding future modes does not require rebuilding the entire project.

Build the system to be reliable, visually useful, educationally grounded, and realistic for the available hardware.

---

## START NOW

Do NOT create code yet.

Do NOT create documentation yet.

First ask me the essential questions you need answered.

After I answer them, take ownership of the architecture and development plan and begin building the project from scratch.