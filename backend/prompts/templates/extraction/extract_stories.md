# version: 1.0.0
# skill: extract-stories
# last_updated: 2026-07-07
# description: Extracts user stories from the stories document, with components context

SYSTEM:
You are extracting user stories for a software project from its stories
document.

COMPONENTS (already extracted):
{{ components_context }}

STORIES DOCUMENT:
{{ stories_doc }}

TASK:
Identify every distinct user story in the document. For each story, report:
- id: the story's identifier as given in the document (e.g. "US-12"); if none
  is given, assign one in the form "US-<n>" numbered in document order
- title: a short title for the story
- description: the story itself (ideally in "As a ... I want ... so that ..."
  form if the source supports it)
- acceptance_criteria: the list of acceptance criteria stated for this story
- related_components: names of any of the components listed above that this
  story touches
- estimated_complexity: "low", "medium", or "high", based on the story's scope
  and the number of components it touches; use "medium" if the source gives no
  basis for a more specific estimate

OUTPUT:
Return the extracted stories as structured output matching the provided schema.
