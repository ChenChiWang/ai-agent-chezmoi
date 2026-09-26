/* Preserve inherited signal state across the Python preparation runtime.
 * No terminal, environment, fd, cwd or process-group changes. */
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 4) return 64; /* python -B controller [controller arguments] */
    uint64_t ignored = 0, blocked = 0;
    sigset_t mask;
    if (sigprocmask(SIG_SETMASK, NULL, &mask)) return 70;
    for (int n = 1; n < NSIG && n < 64; n++) {
        struct sigaction action;
        if (!sigaction(n, NULL, &action) && action.sa_handler == SIG_IGN)
            ignored |= UINT64_C(1) << n;
        if (sigismember(&mask, n) == 1) blocked |= UINT64_C(1) << n;
    }
    char state[48];
    snprintf(state, sizeof(state), "%llx:%llx", (unsigned long long)ignored,
             (unsigned long long)blocked);
    char **next = calloc((size_t)argc + 2, sizeof(char *));
    if (!next) return 70;
    for (int n = 1; n <= 3; n++) next[n - 1] = argv[n];
    next[3] = "--inherited-signals";
    next[4] = state;
    for (int n = 4; n < argc; n++) next[n + 1] = argv[n];
    execv(next[0], next);
    return 70;
}
