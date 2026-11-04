"""`vf capture`: an app's real demo, driven by Playwright on a fake clock, frame by frame, and the HyperFrames camera
that follows one of its elements.

`plan` reads a capture plan (schemas/capture-plan.schema.json) and the app's pinned source
(vitrine/<app>/source.json), `demo` builds the demo at its pinned commit with its scenario variant in a work folder,
`shoot` drives it with the pinned Playwright and Chromium (driver.mjs) and fingerprints what it wrote, `camera` turns
the positions it read into a camera path, and `scene` writes, checks and renders the « camera follow » scene of
templates/hyperframes/.
"""
