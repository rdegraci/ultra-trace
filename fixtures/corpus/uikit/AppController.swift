import UIKit

final class AppController: UIViewController {
    private var token: String?

    override func viewDidLoad() {
        super.viewDidLoad()
        configure()
    }

    func configure() {
        let title = token!
        navigationItem.title = title
    }

    func open(_ url: URL) {
        UIApplication.shared.open(url)
    }
}
