# user-defined map transforms (starlark), loaded by flatten.yaml.

# map a platform string to its ansible_network_os connection value.
ANSIBLE_OS = {
    "eos": "arista.eos.eos",
    "nxos": "cisco.nxos.nxos",
    "ios": "cisco.ios.ios",
}

# map a platform string to its containerlab node kind: the resolved device
# carries its `kind` and the emitter reads it like any other attribute.
CLAB_KIND = {
    "eos": "ceos",
    "nxos": "linux",
}

# strip a CIDR mask off an address, leaving the bare host: `198.51.100.1/24`
# becomes `198.51.100.1`. the flat-inventory emitters want a literal IP, not a
# netbox-style prefixed address.
def cidr_host(v):
    return v.split("/")[0]

def ansible_os(platform):
    if platform not in ANSIBLE_OS:
        fail("no ansible_network_os mapping for platform: " + platform)
    return ANSIBLE_OS[platform]

def clab_kind(platform):
    if platform not in CLAB_KIND:
        fail("no containerlab kind mapping for platform: " + platform)
    return CLAB_KIND[platform]

# avd node type per device role, and the per-device settings avd's node tables
# consume: a numeric id from the name's trailing digits, and the bgp asn per
# role (spines share one, leaves are numbered from a base).
AVD_TYPE = {
    "spine": "spine",
    "leaf": "l3leaf",
}

def avd_type(role):
    if role not in AVD_TYPE:
        fail("no avd node type mapping for role: " + role)
    return AVD_TYPE[role]

def avd_id(name):
    digits = ""
    for c in name.elems():
        if c.isdigit():
            digits += c
        else:
            digits = ""
    if digits == "":
        fail("no trailing digits to derive an avd id from: " + name)
    return int(digits)

def avd_bgp_as(name):
    if name.startswith("spine"):
        return "65100"
    # mlag pair members share one asn: consecutive ids pair up (leaf01+leaf02
    # -> 65101), which the avd emitter lifts to the node group.
    return str(65100 + (avd_id(name) + 1) // 2)

# map the seed's short interface names to eos convention: avd schema-validates
# uplink interfaces against Ethernet[\d/]+, so the mapping owns the rename.
def eos_ifname(name):
    if name.startswith("eth"):
        return "Ethernet" + name[3:]
    return name
