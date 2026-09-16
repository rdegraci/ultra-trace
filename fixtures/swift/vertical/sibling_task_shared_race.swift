// NS4: unprotected shared var across sibling Tasks (dual-timeline witness).

var counter = 0

func bumpA() {
    counter = 1
}

func bumpB() {
    counter = 2
}

func spawnRace() {
    Task {
        bumpA()
    }
    Task {
        bumpB()
    }
}

func spawnThenAwait() async {
    Task {
        bumpA()
    }
    Task {
        bumpB()
    }
    _ = await bumpB()
}

func singleTask() {
    Task {
        bumpA()
    }
}
