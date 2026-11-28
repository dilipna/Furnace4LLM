# Could Furnace work without Docker?

Status: proposal only. No native model engine or isolation fallback is implemented.

Yes: a bundled llama.cpp process could serve the same local requests. That would remove
Docker Desktop, its Linux VM, image downloads and some setup/memory overhead. It would
not automatically preserve Furnace's current network boundary. A loopback listening
address controls incoming connections; it does **not** stop a process calling the internet.

Today the model has a Docker `--internal` network, an unprivileged user, a read-only
root filesystem, dropped capabilities, resource limits and a narrow loopback relay.
The receipt inspects that configuration. It does not establish host-wide isolation,
protect against a compromised Docker daemon, or certify every request's packet history.

## What a native engine would need

| Platform | Candidate replacement | What still needs verification |
| --- | --- | --- |
| Windows | AppContainer without internet capabilities, Job Object resource limits, restricted filesystem access | Whether the selected llama.cpp build and CUDA work in that container; loopback access; child-process restrictions; clean-account packaging and recovery |
| Linux | User/mount/network namespaces, restricted mounts and seccomp | Distribution support, unprivileged namespace policy, GPU device access, default-deny network and packaging |
| macOS | A supported application sandbox and explicit file grants | GPU/Metal support, localhost communication, signing/distribution requirements and the available supported sandbox boundary |

A firewall rule could be another option, but system-wide changes can need administrator
rights and create cleanup/support obligations. “The app promises not to call the internet”
is a policy, not an equivalent replacement for an inspected network boundary.

## Proposed decision gate

1. Prototype on Windows separately, using synthetic data and a pinned engine.
2. Reproduce the existing isolation checks: outgoing connection refusal, restricted file
   access, no privilege escalation, bounded resources, authenticated loopback access,
   crash recovery and clean removal of any policy changes.
3. Test CPU and the owner's GPU on a standard Windows account. Record failures as well
   as successes; do not change the current receipt into a green policy-only indicator.
4. Ask the owner to approve the changed threat model and supported platform before
   offering it. If any check is unavailable, the UI must say **not verified**.

For this milestone Docker remains required for model execution. Document extraction runs
on the host in a resource-limited subprocess; it is not covered by the model's network
isolation. There is no silent switch to a native engine or a cloud endpoint.
