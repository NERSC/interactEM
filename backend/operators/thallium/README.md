Thallium python bindings
========================

Notes
-----

RMA is zero-copy, but SM transport is not. From mercury-hpc dev: 

> RMA is zero-copy but there's always a copy currently for RPC payloads. We might be able to optimize some more by doing what we call a multi-recv optimization where there's a single block allocated on the server where processes can directly memcpy into but that's not something that's been implemented for the sm transport yet. It's not possible however to just pass around buffers, there's always some memcpy involved.

