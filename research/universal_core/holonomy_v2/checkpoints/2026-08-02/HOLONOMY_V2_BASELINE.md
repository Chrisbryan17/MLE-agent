# Holonomy V2 Engineering Baseline

Date: 2026-08-02  
Parent implementation head: `550c24987d86ad03668ed4b49ad74c46ad18d05d`

## Architecture

This baseline adds typed fibers, an immutable program graph, data-derived atoms, a connection graph, explicit closed paths, typed residual reports, bounded candidate growth, rule refinement, a deterministic local tier, and a verified proposal tier.

Accepted programs must replay every demonstration and pass every mandatory closed path before hidden execution. Hidden inputs are not used during induction or ranking. The accepted program and evidence are frozen before predictions are made.

## Engineering gates

- V2 focused tests: 70 passing locally.
- Family regression: 600 of 600 attempted and correct.
- Mutation regression: 400 of 400 attempted and correct.
- Deterministic gate replay: matching.
- Production security scan: clear.
- Authored-text policy scan: clear.

The regression rows vary identifiers, fields, constants, labels, symbols, graph names, board sizes, job data, and demonstration order.

## Preservation

The V1 source identity remains `89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9`.

The protocol identity remains `0194001e82721cd9081aca16bb1c04f34d1c56aa`.

Prior first-attempt records remain unchanged.

## Evidence boundary

These figures are engineering regression, not fresh capability evidence. Run 001 was revealed before this implementation and cannot support a new generalization claim.

The next empirical gate is a new challenge created only after the V2 code identity is frozen. Its first attempt must be retained and published regardless of score.
