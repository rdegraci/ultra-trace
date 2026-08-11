import Foundation

struct Point {
    var x: Int
    var y: Int
}

class Greeter {
    func hello(_ name: String) -> String {
        return "hi \(name)"
    }

    init() {}
}

enum Mode {
    case idle
    case running
}

protocol Named {
    var name: String { get }
}

extension Point {
    func mirrored() -> Point {
        return Point(x: -x, y: -y)
    }
}

func topLevelAdd(_ a: Int, _ b: Int) -> Int {
    return a + b
}
