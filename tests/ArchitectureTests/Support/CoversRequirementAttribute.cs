namespace ArchitectureTests.Support;

/// <summary>
/// Declares that a test method exercises a specific functional requirement, identified by its
/// short id (for example <c>"FR-005"</c>).
/// </summary>
/// <remarks>
/// <para>
/// A generic <c>[Trait("Requirement", "FR-005")]</c> pair would do this with no new type at all,
/// but it buys that convenience at a real cost: the trait's key and value are both bare strings,
/// so nothing stops a typo in the key (<c>"Requirment"</c>) or an inconsistent value format
/// (<c>"FR-5"</c> instead of <c>"FR-005"</c>) from compiling cleanly and running cleanly. The
/// mistake produces a trait that simply never matches whatever later tooling queries for it —
/// there is no error, just quietly missing coverage that looks, from the outside, identical to
/// coverage that was never claimed in the first place.
/// </para>
/// <para>
/// A dedicated attribute type does not validate the id's format either (that is a job for
/// whatever later reads these attributes and checks their values against the actual set of
/// requirement ids), but it does guarantee that every usage is unambiguously a requirement-
/// coverage declaration and not some other trait that happens to share a string key. That is
/// enough to make the coverage claim something a later automated check can walk by reflection,
/// rather than something that only a document asserts.
/// </para>
/// </remarks>
[AttributeUsage(AttributeTargets.Method, AllowMultiple = true)]
public sealed class CoversRequirementAttribute : Attribute
{
    public string RequirementId { get; }

    public CoversRequirementAttribute(string requirementId)
    {
        RequirementId = requirementId;
    }
}
