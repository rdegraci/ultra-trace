// Clearly unsupported for Core spike: freestanding macro expansions.
// The helper should surface these under unsupported category "macro".

func demo() {
    #warning("macro expansion fixture")
}
