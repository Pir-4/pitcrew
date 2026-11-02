# Allure TestOps through its REST API, not allurectl

Pitcrew talks to Allure TestOps only through its REST API (`/api/rs/...`, `Api-Token` auth), even
though `qa_automation` uses `allurectl`. `allurectl` cannot create or update a test plan or run
one, so the REST API was needed anyway; one client instead of two keeps a Go binary out of the
image, lets us limit the service to the few calls it actually needs, and makes the responses easy
to record as pytest fixtures.
