// NS3 fixtures: isolation signals (heuristic; not proven races).

@MainActor
func updateUI(_ text: String) {
    print(text)
}

nonisolated func backgroundWork() {
    updateUI("off-main")
}

@MainActor
final class Screen {
    var title: String = ""

    func setTitle(_ value: String) {
        title = value
    }
}

actor CounterBox {
    func bump(_ screen: Screen) {
        screen.title = "from-actor"
    }
}

func touchShared(_ screen: Screen) {
    screen.title = "from-free"
}
