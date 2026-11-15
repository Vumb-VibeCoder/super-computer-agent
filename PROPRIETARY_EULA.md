# PROPRIETARY SOFTWARE LICENSE AGREEMENT (EULA)

**Scope:** this Agreement governs ONLY the two compiled components below
("the Licensed Binaries"), distributed as `.pyd` (Windows) / `.so`
(Linux) files, together with any accompanying license-key file and
documentation for them. Everything else in the `super-computer-agent`
repository is licensed under AGPL-3.0 (see LICENSE/NOTICE) and is not
affected by this Agreement.

- `canvas_core` — delta-compression engine (source: `canvas_v7.py` and
  predecessor revisions `canvas_v6.py`, `canvas_delta2.py`,
  `canvas_delta3.py`)
- `pixel_grid_core` — live pixel-grid / change-detection engine (source:
  `pixel_grid.py`)

Licensor: asa ("Licensor")
Contact: hoanggiabao40478@gmail.com

BY INSTALLING, COPYING, OR USING THE LICENSED BINARIES, YOU ("LICENSEE")
AGREE TO BE BOUND BY THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT INSTALL
OR USE THE LICENSED BINARIES.

## 1. Grant of License

Subject to full payment of any applicable fees and compliance with this
Agreement, Licensor grants Licensee a non-exclusive, non-transferable,
revocable license to install and execute the Licensed Binaries, solely
in object-code form, strictly limited by the parameters embedded in
Licensee's License Key (see §3).

No source code is provided or licensed. No title to the Licensed
Binaries passes to Licensee; Licensor retains all right, title, and
interest, including all intellectual property rights.

## 2. Restrictions

Licensee shall NOT, and shall not permit or assist any third party to:

a. reverse engineer, decompile, disassemble, decrypt, or otherwise
   attempt to derive the source code, algorithms, or data structures of
   the Licensed Binaries, in whole or in part, except to the limited
   extent such restriction is expressly prohibited by applicable
   mandatory law (e.g., statutory interoperability rights), and then
   only after providing Licensor written notice and a reasonable
   opportunity to provide the needed interoperability information;
b. remove, bypass, disable, or tamper with the License Key validation,
   signature verification, or any other technical protection measure;
c. use the Licensed Binaries on more machines, devices, or with more
   concurrent execution threads/processes than authorized by the
   License Key;
d. sublicense, sell, rent, lease, lend, or otherwise transfer the
   Licensed Binaries or this license to any third party without
   Licensor's prior written consent;
e. use the Licensed Binaries to build a product or service that exposes
   the same functionality as a direct substitute/competing offering,
   except as expressly permitted in a separate written agreement;
f. use the Licensed Binaries in excess of, or outside the purpose
   stated in, the applicable order/quote.

## 3. License Key, Machine Binding, and Offline Signature Verification

a. **License Key.** Each copy of the Licensed Binaries is activated with
   a License Key issued by Licensor. The Key is a signed data structure
   (see §3(c)) encoding: licensee identity, expiration (if any), the
   maximum number of bound machines, and the maximum number of
   concurrent execution threads/processes permitted.
b. **Machine/thread binding.** On first activation, the Licensed
   Binaries derive a Machine ID (e.g., a hash of stable hardware/OS
   identifiers) and record it, together with the Key, in a local
   license store. The Licensed Binaries refuse to run, or terminate at
   startup, if: (i) the Machine ID does not match a Machine ID bound to
   the Key, (ii) the number of distinct bound machines would exceed the
   Key's limit, or (iii) the number of concurrently running
   threads/processes exceeds the Key's limit.
c. **Offline signature verification.** The Key is signed by Licensor
   with an asymmetric algorithm (e.g., Ed25519); only the corresponding
   public key is embedded in the Licensed Binaries. Verification is
   performed entirely offline, at process start and at periodic
   intervals thereafter, against this embedded public key — no network
   call to Licensor is required or made. A Key that fails signature
   verification, is expired, or is bound to a different Machine ID is
   treated as absent, and the Licensed Binaries will refuse to operate.
d. Licensee shall not share, publish, or attempt to generate License
   Keys other than those issued by Licensor.

## 4. Ownership

The Licensed Binaries are licensed, not sold. All copyright, trade
secret, and other intellectual property rights in the Licensed Binaries
and their underlying (unpublished) source code remain exclusively with
Licensor. This Agreement grants no rights other than those expressly
stated in §1.

## 5. Confidentiality

The Licensed Binaries and all associated algorithms, design
information, and benchmarks disclosed by Licensor are Licensor's
confidential information and trade secrets. Licensee shall protect them
with at least the same degree of care it uses for its own confidential
information of similar importance, and in no case less than reasonable
care, and shall not disclose them to any third party except as
permitted under §2.

## 6. Term and Termination

This Agreement is effective upon first use of the Licensed Binaries and
continues until terminated. Licensor may terminate immediately upon
written notice if Licensee breaches any provision of this Agreement,
including the restrictions in §2 or §3. Upon termination, Licensee must
immediately cease all use of the Licensed Binaries and destroy all
copies in its possession or control. Sections 2, 4, 5, 7, 8, and 9
survive termination.

## 7. Disclaimer of Warranty

THE LICENSED BINARIES ARE PROVIDED "AS IS," WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT. LICENSOR DOES NOT WARRANT THAT OPERATION OF THE
LICENSED BINARIES WILL BE UNINTERRUPTED OR ERROR-FREE.

## 8. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL
LICENSOR BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL,
OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, DATA, OR GOODWILL, ARISING
OUT OF OR RELATED TO THIS AGREEMENT OR THE LICENSED BINARIES, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. LICENSOR'S TOTAL AGGREGATE
LIABILITY UNDER THIS AGREEMENT SHALL NOT EXCEED THE AMOUNT ACTUALLY PAID
BY LICENSEE FOR THE LICENSE GIVING RISE TO THE CLAIM.

## 9. General

a. **Export/Sanctions.** Licensee shall comply with all applicable
   export-control and sanctions laws.
b. **Governing law.** This Agreement is governed by the laws of the
   Socialist Republic of Vietnam, without regard to its conflict-of-law
   rules. Any dispute arising out of or in connection with this Agreement
   shall first be settled by friendly negotiation; failing that, it shall
   be submitted to the competent People's Court of Vietnam, unless the
   parties separately agree in writing to resolve it by arbitration under
   the rules of the Vietnam International Arbitration Centre (VIAC).
c. **Entire agreement.** This Agreement, together with any order/quote
   referencing it, is the entire agreement between the parties
   regarding the Licensed Binaries and supersedes all prior agreements
   on this subject.
d. **Severability.** If any provision is held unenforceable, the
   remainder of this Agreement remains in effect, and the unenforceable
   provision shall be reformed to the minimum extent necessary to make
   it enforceable while preserving its intent.
e. **No waiver.** Failure to enforce any provision is not a waiver of
   the right to enforce it later.
f. **Contact.** All notices under this Agreement shall be sent to
   hoanggiabao40478@gmail.com.

---

### Implementation notes (non-contractual — engineering reference only)

This section is guidance for Licensor's own build pipeline, not a term
of the Agreement above.

- **Signing:** generate an Ed25519 keypair offline; embed only the
  public key in the compiled binary (e.g., baked into the `.pyd`/`.so`
  via the build step, not shipped as a separate readable file).
  License Key payload (JSON, then signed): `{licensee, issued_at,
  expires_at, max_machines, max_threads, key_id}`. Ship the Key as
  `base64(payload) + "." + base64(signature)`.
- **Verification:** at process start, load the embedded public key,
  verify the signature over the payload, check `expires_at` against
  system clock (accept it's spoofable offline — that's a known
  trade-off of pure offline licensing), check the current Machine ID
  against the bound list stored alongside the Key, check current
  thread/process count against `max_threads`. Re-check periodically
  (e.g., every N minutes) in a background watchdog so a key swapped
  mid-process is caught.
- **Machine ID:** hash a small set of relatively stable identifiers
  (e.g., disk volume serial + CPU identifier + OS install ID); store
  the hash, not the raw identifiers.
- **Compiling to `.pyd`/`.so`:** build `canvas_v7.py` and
  `pixel_grid.py` with Cython or Nuitka into native extension modules
  so the published repository only ships a thin Python wrapper that
  imports the compiled module; the AGPL-3.0 code calls into it like any
  other third-party extension.
- **Beyond this:** compiling with Cython/Nuitka and offline Ed25519
  signature checking raises the bar for casual inspection but is not
  equivalent to commercial anti-tamper/obfuscation products (e.g.
  VMProtect, Themida, PyArmor). If stronger protection is required,
  that needs a dedicated commercial packer layered on top of the
  compiled binary — this document does not cover building one.
