"""The studio board: one Hermès kanban card per video, from the idea to the publication (issue #7).

`stations` decides, from a card and the state of its video, what happens next (pure functions); `board` talks to the
board through the Hermès CLI; `lanes` carries the decisions out (the code lanes run `vf`, only the Script station asks
the `studio-writer` profile for a draft); `page` serves the upload and gesture page on the tailnet.
"""
