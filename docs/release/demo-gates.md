# Evidence required before calling the demo ready

The product serves model researchers who need the surrounding infrastructure.
The current deliverable is a free local application preview. Its useful first
outcome is an inspected project and an exported kit. It also offers explicitly
prepared local Docker model recipes or a connector to a researcher-operated server. It does not yet supply the managed
infrastructure promised by the planned subscription.

More interface features do not close that gap. Use the following ordered gates
so a working transport fixture cannot be presented as a supported research model.

| Gate | Current evidence | Remaining condition |
| --- | --- | --- |
| Recoverable local application | Actual state, file/lock, failure/retry and restart tests; PR #10's exact-head hosted checks pass. | PR #10 merged as `9059479`; review combined lifecycle corrections before release. |
| Simple website and Studio | Desktop/mobile source browser journeys, imports, exports, stale-response handling and accessible native disclosures. | Review the dependent UI PR and its exact-head hosted checks. Public hosting stays recorded-only. |
| Installable preview | Updated wheel ZIP passed initially empty-cache Linux/Windows installation and restart checks. Clean Linux source setup passed separately. | Human fresh-profile onboarding, particularly Windows; native installer remains unavailable. |
| Understandable experience | Separate independent/assisted participant tasks in the interface handoff; observations blank. | Owner must actually perform the tasks and supply observations. Automation cannot establish comprehension. |
| Bounded real-model evidence | Two small pinned recipes have historical records on one Windows/Docker machine; [results and limits](../product/real-model-validation.md). | Validate the final integrated build on the intended machine before claiming current-build support. Rule scores are not semantic quality. |
| Managed demo | Local single-user supervisor implements preparation, authenticated serving, readiness, evaluation and cleanup. | Hosted multi-user service, billing, isolation and costs remain unimplemented and inactive. Local integration is not hosted readiness. |
| Release | Historical measurements remain verifiable, with no new inference claims. | Explicit merge/release/deployment authorization and reviewed public artifacts. |

Do not infer architecture support from filenames, protocol compatibility, upstream
engine documentation, case exact matches or a passing HTTP fixture. Retain failed,
unscored and interrupted outcomes. Add a second model only after one complete
supported lifecycle is measured and documented. Billing, paid servers, native
installers and new model adapters are outside the current integration operation.

See [the source-bound interface handoff](simple-interface-review.md) for commands,
receipts, human tasks and recorded-versus-live limitations. The next product
gate after review is human onboarding plus final-build validation on the intended
machine. Neither is replaced by automated browser tests or historical records.
