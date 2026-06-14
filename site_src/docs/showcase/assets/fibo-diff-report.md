## 🔴 owlcompare diff: 28 breaking changes

Compared `examples/fibo_demo/v1/OwnershipAndControl/Executives.rdf` against `examples/fibo_demo/v2/OwnershipAndControl/Executives.rdf`.

### Breaking changes (28)

- 🔴 **Class reparented:** `fibo-be-oac-exec:Authorization`: fibo-fnd-pty-pty:Situation → cmns-pts:Situation (lateral)
- 🔴 **Class reparented:** `fibo-be-oac-exec:AuthorizingParty`: fibo-fnd-pty-pty:Actor → cmns-pts:Actor (lateral)
- 🔴 **Class reparented:** `fibo-be-oac-exec:ResponsibleParty`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole (lateral)
- 🔴 Property fibo-be-oac-exec:authorizes reparented: fibo-fnd-pty-pty:actsOn → cmns-pts:actsOn (lateral)
- 🔴 Property fibo-be-oac-exec:authorizesThrough reparented: fibo-fnd-pty-pty:actsIn → cmns-pts:actsIn (lateral)
- 🔴 Property fibo-be-oac-exec:hasAuthorizedParty reparented: fibo-fnd-pty-pty:hasUndergoer → cmns-pts:hasUndergoer (lateral)
- 🔴 Property fibo-be-oac-exec:hasAuthorizingParty reparented: fibo-fnd-pty-pty:hasActor → cmns-pts:hasActor (lateral)
- 🔴 Property fibo-be-oac-exec:hasResponsibleParty reparented: fibo-fnd-pty-pty:hasPartyInRole → cmns-pts:hasPartyRole (lateral)
- 🔴 Property fibo-be-oac-exec:isAuthorizedBy reparented: fibo-fnd-pty-pty:isAffectedBy → cmns-pts:isAffectedBy (lateral)
- 🔴 Property fibo-be-oac-exec:isAuthorizedThrough reparented: fibo-fnd-pty-pty:undergoes → cmns-pts:undergoes (lateral)
- 🔴 **Restriction added on** `fibo-be-oac-exec:AuthorizedParty`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson cmns-rlcmp:isPlayedBy`
- 🔴 **Restriction added on** `fibo-be-oac-exec:AuthorizingParty`: `exactly 1 fibo-be-le-lp:LegalPerson cmns-rlcmp:isPlayedBy`
- 🔴 **Restriction added on** `fibo-be-oac-exec:BoardMember`: `cmns-rlcmp:isPlayedBy some _restriction:31f4e449`
- 🔴 **Restriction added on** `fibo-be-oac-exec:BoardMember`: `cmns-rlcmp:isPlayedBy some _restriction:677f82c9`
- 🔴 **Restriction added on** `fibo-be-oac-exec:BoardOfDirectors`: `cmns-rlcmp:isPlayedBy some _restriction:61683090`
- 🔴 **Restriction added on** `fibo-be-oac-exec:BoardOfDirectors`: `cmns-rlcmp:isPlayedBy some _restriction:df84ca4c`
- 🔴 **Restriction added on** `fibo-be-oac-exec:ChiefExecutiveOfficer`: `cmns-rlcmp:isPlayedBy some _restriction:3b9be241`
- 🔴 **Restriction added on** `fibo-be-oac-exec:Executive`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson cmns-rlcmp:isPlayedBy`
- 🔴 **Restriction added on** `fibo-be-oac-exec:LegallyDelegatedAuthority`: `cmns-rlcmp:isPlayedBy all fibo-be-le-lp:LegalPerson`
- 🔴 **Restriction added on** `fibo-be-oac-exec:ResponsibleParty`: `cmns-rlcmp:isPlayedBy all fibo-be-le-lp:LegallyCompetentNaturalPerson`
- 🔴 **Restriction added on** `fibo-be-oac-exec:ResponsibleParty`: `cmns-rlcmp:isPlayedBy some _restriction:7c75f7a4`
- 🔴 **Restriction added on** `fibo-be-oac-exec:Signatory`: `cmns-rlcmp:isPlayedBy some _restriction:f5080d14`
- 🔴 **Domain changed on** `fibo-be-oac-exec:elects`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole
- 🔴 **Domain changed on** `fibo-be-oac-exec:hasResponsibility`: fibo-fnd-pty-pty:IndependentParty → cmns-pts:Party
- 🔴 **Domain changed on** `fibo-be-oac-exec:nominates`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole
- 🔴 **Range changed on** `fibo-be-oac-exec:elects`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole
- 🔴 **Range changed on** `fibo-be-oac-exec:nominates`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole
- 🔴 Complex class expression on fibo-be-oac-exec:BoardCapacity changed (deep)

### Other changes (13)

- 🟡 **Restriction removed from** `fibo-be-oac-exec:AuthorizedParty`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson fibo-fnd-rel-rel:hasIdentity`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:AuthorizingParty`: `exactly 1 fibo-be-le-lp:LegalPerson fibo-fnd-rel-rel:hasIdentity`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:BoardMember`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:9d105bc6`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:BoardMember`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:f392b2eb`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:BoardOfDirectors`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:7d909b88`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:BoardOfDirectors`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:61683090`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:ChiefExecutiveOfficer`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:3b9be241`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:Executive`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson fibo-fnd-rel-rel:hasIdentity`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:LegallyDelegatedAuthority`: `fibo-fnd-rel-rel:hasIdentity all fibo-be-le-lp:LegalPerson`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:ResponsibleParty`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:7c75f7a4`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:ResponsibleParty`: `fibo-fnd-rel-rel:hasIdentity all fibo-be-le-lp:LegallyCompetentNaturalPerson`
- 🟡 **Restriction removed from** `fibo-be-oac-exec:Signatory`: `fibo-fnd-pty-rl:isPlayedBy some _restriction:f5080d14`
- ⚪ **Ontology metadata:** `skos:changeNote` *""* → *"The https://spec.edmcouncil.org/fibo/ontology/BE/20230301/OwnershipAndControl/Executives.rdf version of the ontology was modified to replace content that is now available in the OMG Commons Ontology Library \(Commons\) v1.1 \(FND-380\)."*

<details>
<summary>📜 10 unexplained Layer 0 changes</summary>

- 🟡 Removed: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> owl:imports <https://spec.edmco…`
- 🟡 Removed: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> owl:imports <https://spec.edmco…`
- ⚪ Removed: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> owl:versionIRI <https://spec.ed…`
- 🟡 Removed: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> cmns-av:copyright "Copyright (c…`
- 🟡 Removed: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> cmns-av:copyright "Copyright (c…`
- 🟡 Added: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> owl:imports <https://www.omg.org/…`
- 🟡 Added: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> owl:imports <https://www.omg.org/…`
- ⚪ Added: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> owl:versionIRI <https://spec.edmc…`
- 🟡 Added: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> cmns-av:copyright "Copyright (c) …`
- 🟡 Added: `<https://spec.edmcouncil.org/fibo/ontology/BE/OwnershipAndControl/Executives/> cmns-av:copyright "Copyright (c) …`
</details>

---
*Generated by owlcompare 0.0.1 · [Schema](docs/schema/diff-result.schema.json) · Run with --format json for machine-readable output*
