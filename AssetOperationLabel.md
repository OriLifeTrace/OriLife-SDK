# Metadata label 1113: asset operation record

OriLife records farm produce as Cardano native tokens under [CIP-0113](https://github.com/cardano-foundation/CIPs/tree/master/CIP-0113) (programmable tokens). Examples are a tree or a single fruit. Every transaction that OriLife's transaction builder produces for these tokens carries one small metadata entry under label **1113**. The entry says what kind of operation it is, so explorers, indexers and usage counters can tell these transactions apart without decoding scripts.

Docs: [orilife.io](https://orilife.io)

## Format

```cddl
asset_operation = {
  "v"  : 1,       ; format version
  "op" : tstr     ; "mintBatch", "transfer" or "manage"
}
```

Example, in CBOR diagnostic notation:

```
{ 1113: { "v": 1, "op": "transfer" } }
```

- The map has exactly these two keys.
- It carries **no personal data and no asset data**: no names, no farm location, no photos, no prices.
- `op` is one of three names: `mintBatch` when new tokens are issued, `transfer` when a token changes owner, and `manage` for any other operation. A new name, or any change to the shape, increments `v`.
- No on-chain script reads this entry. It is informational, and a transaction without it is still valid.
- It adds about 55 bytes to a transaction, roughly 2,400 lovelace in fees.

## How this relates to labels 1454 and 1455

Labels 1454 and 1455 anchor **records**: the hash of an observation and the root of an event history. [VERIFY.md](VERIFY.md) explains how to check them. Label 1113 marks **token operations**.

The two are independent. A record can be anchored without any token, and the label-1113 entry itself carries no record.

## Status

- The label registration is [cardano-foundation/CIPs#1283](https://github.com/cardano-foundation/CIPs/pull/1283).
