Your second project: Live Concept Visualizer / Canvas of Imagination
This is a considerably more ambitious direction than your first project.

And I have an important finding: Almost every individual capability you described has been attempted or implemented somewhere. However, the combination of continuous teacher speech, scientifically accurate interactive simulations, unrestricted imaginative scene generation and live story narration is a more specific product vision.

I found some particularly close projects, including one that almost exactly matches your speech-to-visual storytelling idea.

Let's examine each part separately.
1. Your idea, broken into three products
I understand your proposal as three engines operating under one application.
Module 1
Live Concept Simulator




















7










The teacher speaks:

"Imagine a box placed on an inclined plane at 30 degrees."

Your application identifies the physics concept, creates the appropriate environment, applies the relevant equations and shows the box moving with its force vectors.

The teacher continues:

"Now increase the angle to 45 degrees."

The simulation updates accordingly.

The important feature: The visuals aren't merely generated pictures. They represent a mathematical or scientific model, with behaviour governed by appropriate equations.

Module 2
Canvas of Imagination































The teacher says:

"Imagine a donkey riding a bicycle."

It appears on the classroom screen.

"Now imagine the donkey wearing sunglasses and travelling through space."

The visual changes.

The teacher can describe virtually anything, and the application generates the scene.

The important feature: Open-ended creative visualisation rather than being restricted to a library of predefined diagrams.

Module 3
Live Story Narrator




















12










The teacher narrates:

"Once upon a time, a boy lived in a small village near a forest..."

As the story progresses, the application generates corresponding scenes. When the boy enters the forest, the displayed scene changes. When a dragon appears, the dragon appears on screen.

The narration continues while the visuals follow the story.

The important feature: Maintaining characters, environments, events and narrative continuity rather than generating unrelated pictures for every sentence.


These are three distinct technical challenges. Combining them into a unified classroom experience is the interesting part.

2. Has the Live Concept Simulator already been implemented?
Very substantial overlap exists
I found several relevant products and research projects.
A. Viditra




















10










Website: viditra.co

This is one of the closest classroom products to your first module.

It advertises:
- 96 live simulations in 2D and 3D.
- Physics, chemistry and mathematics.
- Interactive physics calculated from equations.
- Teachers can move through simulation states, pause, reorder and draw over the simulation.
- Simulations designed around the Indian NCERT syllabus.
Its positioning is particularly interesting: the teacher explains through speech while the simulation displays the physics. 
Viditra


The distinction: Viditra's published workflow is to choose a concept and teach through its prepared simulations. I found no evidence in its public description that it continuously listens to arbitrary teacher speech and constructs new simulations from it.

That is a meaningful difference.
B. Interactive Physics Version 10







devpost.com


Website: design-simulation.com

This is an especially important discovery.

On May 21, 2026, Design Simulation Technologies announced an AI assistant that lets teachers and students describe a physics experiment in ordinary English.

For example:

"Build a pendulum 30 cm long with a 200 gram bob and graph its kinetic and potential energy."

The AI creates the objects, constraints and measurement instruments, then runs the physics simulation. 
design-simulation.com


That is very close to your natural-language-to-physics-simulator idea.

The distinction: The advertised workflow is prompt-driven simulation creation, rather than continuous classroom microphone input that follows a teacher's changing explanation.
C. Gemini interactive simulations







ppc.land


Google announced this functionality on August 24, 2026.

Gemini can transform a question or complex topic into custom interactive visualisations. Google specifically mentions rotating molecules and simulating complex physics systems. 
Workspace Updates Blog+1


This is important because your concept is no longer limited to specialist simulation software. General-purpose AI assistants are moving towards generating interactive learning material on demand.

The distinction: A user asking Gemini to create a simulation is not necessarily equivalent to a teacher speaking continuously during a lecture and having the simulation adapt to the evolving explanation.
D. Bodhan.AI
Website: simulations.bodhan.ai

Its advertised functionality is particularly relevant: describe a concept in a prompt and generate an interactive simulation for students. The website gives a convex-lens simulation as an example. 
simulations.bodhan.ai


This is another example of natural-language-driven educational simulation creation.
What I conclude about module 1
Your broad concept definitely exists in parts.
Capability	Already demonstrated by existing work?
Pre-built interactive physics simulations	Yes
Equations controlling physics animation	Yes
Natural-language description to physics simulation	Yes
AI-generated interactive educational visuals	Yes
Continuous live teacher speech controlling new simulations	I did not verify an exact matching commercial implementation
Switching between concepts and updating simulations during a live lecture	Not established as a unique capability

The potential differentiator is the live speech-to-science-model pipeline, not the idea of AI creating physics simulations.
3. Has the Canvas of Imagination already been implemented?
Very close matches found
This module is where things get particularly interesting.
A. live-visuals




















8










Repository: github.com/timegravity/live-visuals

This is probably the single closest match to your overall speech-driven visualisation idea.

Its developer describes it as:
- Speak into a microphone.
- Transcribe speech.
- Classify each sentence into a type of visual.
- Generate charts, diagrams, text cards, photographs or scenes.
- Animate scenes when the input is storytelling.
- Display results within a few seconds.
It has an explicit story mode. The README reports a generated still image in approximately 2–3 seconds, followed by a short animated clip moments later. 
timegravity/live-visuals · GitHub+1


Its architecture also resembles the type of system you are imagining:
Live microphone input


Speech recognition


Local LLM: sentence classification


Charts


Diagrams


Scenes




Live visual display


This is an actual open-source implementation, not just a conceptual research proposal.

There are, however, important limitations:
- Its full configuration specifies an NVIDIA GPU with 48 GB VRAM. Its reduced still-image configuration is described as requiring roughly 20 GB.
- The developer reports that the animation can be interrupted when new sentences arrive rapidly.
- It is designed as a personal presentation tool with one session at a time.
- Its developer says the commercial Live product is currently offline while being upgraded, although the visual engine is open source under MIT. 
  timegravity/live-visuals · GitHub+1
What it means for your idea: Simply converting anything someone says into generated visual scenes is no longer a defensible claim of novelty.

But this implementation does not establish that it can produce accurate, equation-governed physics simulations from arbitrary spoken explanations.
B. Scribbling Speech







xinyue.de


Website: Google Scribbling Speech

This is an older but highly relevant Google experiment from September 2018.

Its stated purpose was to turn real-time free speech into animated drawings. It explored speech recognition, machine learning and recurrent neural networks to generate imaginary visual worlds that follow a narrator. 
Experiments with Google+1


That is remarkably close to your original intuition for the Canvas of Imagination.

It means the general concept has existed for years, even though the technology and product possibilities have changed considerably.
C. Genie 4
Research preview




















9










Website: Google DeepMind Genie 4

This is a very recent development, announced on October 27, 2026.

Genie 4 is designed to generate interactive worlds that users can modify through natural-language prompts.

For example, users can change weather, introduce objects or characters, move cameras and alter the evolving environment. Google also describes physical interactions such as collisions and aerodynamics. 
Google DeepMind+1


This is particularly relevant to your donkey-on-a-bicycle example.

A world-generation model can create an imaginative scene and allow it to evolve interactively, rather than merely producing one static image.

But there are two important qualifications:
1. Genie 4 is currently an early research preview available to trusted testers, not a generally available classroom product.
2. Google acknowledges that complex physical interactions, spatial accuracy, object permanence and long-term consistency still need improvement. 
   Google DeepMind
It also does not establish continuous microphone-driven teacher narration as its input workflow. Its published interaction examples use text prompts.

My conclusion about Canvas of Imagination: The broad idea already exists in several forms. The interesting opportunity is making it an easy, persistent, voice-controlled teaching canvas that can respond to a teacher naturally.

4. Has Live Story Narrator already been implemented?
Yes, close implementations exist
There are two particularly relevant examples.
First: live-visuals Story Mode
The same open-source repository discussed above explicitly describes story narration being turned into illustrated scenes, followed by short animations.

Its system even uses a genre mechanism to distinguish storytelling from ordinary business or explanatory speech. 
timegravity/live-visuals · GitHub+1


That is very close to your third module.
Second: OpenMAIC







amd.com


Website: openmaic.lol

OpenMAIC produces interactive lessons with AI teacher narration, slides, shared whiteboards, visualisations and simulations.

It can turn documents and topics into structured learning experiences, and has different classroom modes. 
OpenMAIC


It is primarily an AI-led classroom rather than an application continuously visualising a human teacher's spontaneous storytelling.
What is actually difficult about your story narrator?
Generating an image of a boy entering a forest is relatively straightforward.

Generating the right sequence of images as a story unfolds is harder.

Imagine the teacher says:
1. A boy enters a forest.
2. He sees a tiger.
3. He starts running.
4. The tiger follows him.
5. He climbs a tree.
Your application must preserve:
- The boy's appearance.
- The tiger's appearance.
- The same forest environment.
- The position and progression of characters.
- The chronological sequence.
- The relationship between previous and current scenes.
Otherwise, the boy might change clothes, the tiger might become a lion, and the forest might turn into a city between sentences.

That is a narrative-continuity problem. It deserves its own technical design.

5. One more discovery: the academic research landscape
A particularly relevant 2026 survey is:

Capabilities of Generative Artificial Intelligence and Three-Dimensional Visualizations in Education: A Survey of Recent Systems.

It was published on July 21, 2026, in Computer Applications in Engineering Education. The authors reviewed 48 studies. 
Wiley Online Library


Its findings are useful for understanding where your opportunity lies:
- AI educational systems predominantly focus on content generation and instructional support.
- 3D systems tend to focus on immersive learning and spatial understanding.
- Only a handful of projects combine these directions, and most are still prototypes.
- Teacher review and refinement of AI-generated material remain relatively uncommon. 
  Wiley Online Library
Another relevant research project is Carnegie Mellon University's PAT3D, published in March 2026.

It uses AI to create physically plausible, simulation-ready 3D environments from text descriptions. It combines scene generation, visual reasoning and a physics simulator to correct physical inconsistencies. However, the reported scene generation time is 10–30 minutes, not live classroom generation. 
CMU School of Computer Science+1


This is an important distinction: Generating something that looks physically plausible and generating something that behaves according to the correct physics are not the same task.
6. There is an interesting project called Visigen too
One more discovery deserves attention.

Visigen:

GitHub: Visigen

It converts written physics problems into interactive 3D physics simulations.

The described pipeline is:
1. Understand the natural-language physics problem.
2. Extract parameters such as mass, friction and angle.
3. Generate a structured 3D scene.
4. Validate and refine the scene using an AI feedback loop.
5. Run the simulation using React Three Fiber and the Rapier physics engine.

GitHub
This is particularly close to your inclined-plane and rain-relative-velocity examples.

It is another reason not to claim that natural-language-to-physics-simulation is an entirely new invention.

7. Where is the actual opportunity for your idea?
Here is my consolidated comparison.
Your proposed feature	Closest existing implementation	What remains interesting
Live physics visualisation	Viditra	Generating simulations from spontaneous teacher speech
Text/speech to physics simulation	Interactive Physics V10, Visigen	Continuous updates and lecture-context awareness
Open-ended imaginative scenes	Live-visuals, Genie 4	Classroom-oriented voice-controlled persistent world
Story narration with generated visuals	Live-visuals, Scribbling Speech	Longer narrative continuity and teaching controls
Interactive 3D educational scenes	TeachSpark, Gemini	Combining teacher speech with dependable simulations
Full unified three-mode classroom product	No exact equivalent verified in this search	A potentially differentiated integration

I want to emphasise one thing:

I have not established that nobody has implemented the complete combination. A product, private prototype or research project could exist without being easily discoverable. This is a preliminary competitive review, not an exhaustive worldwide prior-art or patent search.

Nevertheless, I did not find a publicly verified implementation demonstrating all three of your modes operating together through continuous human teacher speech in one classroom application.

That is a more defensible observation than claiming the entire concept is unprecedented.
8. How I would actually build this
I would not build three completely separate AI applications.

I would build one common speech and orchestration system with three specialised visual engines.
Voice-Native Teaching Environment
Teacher speaks naturally

Continuous microphone input


Shared AI processing engine

Speech recognition · Context tracking · Intent understanding · Scene planning


Science

Equation-based simulation


Imagination

Open-ended scene generation


Stories

Narrative visualisation




Unified classroom display

Interactive · Editable · Controllable · Projector-ready

Suggested architecture, not an existing implementation.
The most important engineering decision
Do not let the LLM directly invent the physics.

Use the LLM to understand the teacher's language and convert it into a structured representation. Use deterministic mathematics and simulation engines to calculate and render the behaviour.

For example, the teacher says:

"A man is running in the rain with an umbrella at 3 metres per second. Rain falls at 5 metres per second at 30 degrees."

Your system should:
1. Identify the man, rain, umbrella and their motion.
2. Extract speeds, directions and angle.
3. Establish the coordinate system and clarify whether the rain angle is measured from the vertical or horizontal.
4. Calculate the velocity vectors and relative velocity.
5. Render the man, moving raindrops, their trajectories and the appropriate vector diagram.
6. Update everything when the teacher changes a speed or direction.
The numerical calculations must come from the actual equations, not an AI-generated video that merely looks convincing.

This is the difference between a visual demonstration and a real physics learning simulator.
Technology directions worth investigating
Component	Technologies to explore
Speech recognition	faster-whisper, streaming ASR
Language understanding	LLMs, structured output, tool calling
2D visualisation	Canvas, SVG, Manim
3D rendering	Three.js, React Three Fiber
Physics simulation	Rapier, Box2D, Bullet
Generated scenes	Diffusion models, image-to-video, interactive world models
State and continuity	Scene graphs, entity IDs, event history
Classroom interface	WebSockets, FastAPI, browser display

You do not need all of these immediately. The architecture should allow different rendering engines to work under the same speech-processing system.

9. Which part should you develop first?
I would rank them as follows.









My first choice
Live Concept Simulator

Highest priority. It has an objective technical foundation, measurable correctness and a clear use case in schools, colleges and educational technology.












Live Story Narrator

Second priority. It can create an engaging teaching experience and could be especially useful for school education, languages and history.












Canvas of Imagination

Third priority. It is visually exciting, but generic prompt-to-image and prompt-to-video systems already cover much of this territory. Your advantage must come from voice interaction, persistent scenes and classroom integration.



My suggestion is to begin with mechanics and physics, perhaps 10–15 well-defined concepts.

For instance: inclined plane, projectile motion, relative velocity, pulley systems, pendulums, circular motion and collisions.

Make those exceptionally reliable before expanding to chemistry, biology, storytelling and unrestricted imagination.

10. Does this change my opinion of your first project?
Yes, quite significantly.

You now have two related project directions:

Project 1: Multimodal AI Teaching Copilot

Converts live teacher speech into organised, continuity-aware slides and study materials.

Project 2: Live Concept Visualizer

Converts live teacher speech into interactive scientific simulations, generated visual scenes and narrated stories.

Rather than treating these as unrelated applications, I see a potential larger product:
An AI Teaching Environment
A classroom where explanations become experiences.







blog.teachmint.com


AI Slide Copilot

Structured lesson generation


Concept Simulator

Scientific visual experiences


Imagination Canvas

Open-ended scene generation


Story Narrator

Narrative visual experiences




A teacher should not need to decide which application to open, which diagram to search for or how to create a simulation.

They should simply be able to teach.

The system should understand what kind of visual experience is needed and produce it.

That is a more interesting product vision than just building another AI slide generator.
11. My honest verdict
I would give the second idea a high score for ambition, but I would separate the product's potential from its novelty.
Dimension	My assessment
Educational usefulness	Very high potential
Technical complexity	Very high
Research potential	High
Commercial potential	Promising, but unvalidated
Broad conceptual novelty	Low
Potential novelty in integrated architecture	Worth investigating
Feasibility for one B.Tech student	Build incrementally, not all at once

The biggest opportunity I see is not generating pretty pictures. It is enabling a teacher to move seamlessly between scientific simulation, abstract visualisation and creative storytelling through natural speech.

That is a real engineering challenge.

And the 2026 research landscape suggests that reliable integration of generative AI, interactive simulation and teacher-controlled learning remains an active area of development. 
Wiley Online Library+2