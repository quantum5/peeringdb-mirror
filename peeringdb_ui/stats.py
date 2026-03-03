def get_fac_stats(netfac, ixfac):
    return {
        "networks": netfac.filter(status="ok").count(),
        "ix": ixfac.filter(status="ok").count(),
    }


def get_ix_stats(netixlan, ixlan):
    peer_count = netixlan.values("net").distinct().filter(status="ok").count()
    connections_count = netixlan.filter(ixlan=ixlan, status="ok").count()
    open_peer_count = (
        netixlan.values("net")
        .distinct()
        .filter(net__policy_general="Open", status="ok")
        .count()
    )
    ipv6_percentage = 0
    total_speed = 0

    try:
        ipv6_percentage = int(
            (
                    netixlan.filter(status="ok", ixlan=ixlan, ipaddr6__isnull=False).count()
                    / netixlan.filter(ixlan=ixlan, status="ok").count()
            )
            * 100
        )
    except ZeroDivisionError:
        pass

    for n in netixlan.filter(status="ok", ixlan=ixlan):
        total_speed += n.speed

    return {
        "peer_count": peer_count,
        "connection_count": connections_count,
        "open_peer_count": open_peer_count,
        "ipv6_percentage": ipv6_percentage,
        "total_speed": total_speed,
    }
