from typing import List, Dict, Optional
from ..schemas import QuizQuestion, QuizResult, QuizReviewItem, PublicQuizQuestion
from .scoring_engine import DeterministicScoringEngine, GRADE_WEIGHTS
from ..skills import normalize_skill

SAMPLE_QUIZZES: Dict[str, List[QuizQuestion]] = {
    "Python": [
        # Basic (1-5)
        QuizQuestion(
            id="py_b1", skill="Python", difficulty="Basic",
            question="What is the time complexity of looking up a key in a Python dict on average?",
            options=["O(1)", "O(n)", "O(log n)", "O(n^2)"],
            correct_index=0, explanation="Python dictionaries use hash tables with O(1) average lookup."
        ),
        QuizQuestion(
            id="py_b2", skill="Python", difficulty="Basic",
            question="Which data structure is immutable in Python?",
            options=["List", "Dictionary", "Tuple", "Set"],
            correct_index=2, explanation="Tuples cannot be altered once instantiated."
        ),
        QuizQuestion(
            id="py_b3", skill="Python", difficulty="Basic",
            question="What keyword creates a generator function in Python?",
            options=["return", "yield", "async", "generate"],
            correct_index=1, explanation="The 'yield' keyword turns a standard function into a generator iterator."
        ),
        QuizQuestion(
            id="py_b4", skill="Python", difficulty="Basic",
            question="How do you handle exceptions safely in Python?",
            options=["try / except", "catch / throw", "begin / rescue", "test / fail"],
            correct_index=0, explanation="Python uses 'try' and 'except' blocks for exception catching."
        ),
        QuizQuestion(
            id="py_b5", skill="Python", difficulty="Basic",
            question="What does PEP 8 define in the Python ecosystem?",
            options=["Package installation standards", "Style Guide for Python Code", "Memory garbage collection rules", "GIL implementation"],
            correct_index=1, explanation="PEP 8 is the canonical style guide for Python programming."
        ),

        # Intermediate (6-10)
        QuizQuestion(
            id="py_i1", skill="Python", difficulty="Intermediate",
            question="What is the purpose of Python's Global Interpreter Lock (GIL)?",
            options=[
                "Prevent race conditions in multi-process memory",
                "Ensure thread-safe memory management for CPython reference counting",
                "Speed up CPU-bound mathematical operations across cores",
                "Compile Python bytecode directly to LLVM"
            ],
            correct_index=1, explanation="The GIL prevents multiple native threads from executing Python bytecodes simultaneously in CPython."
        ),
        QuizQuestion(
            id="py_i2", skill="Python", difficulty="Intermediate",
            question="What will `[*[1, 2], *[3, 4]]` produce in Python 3.5+?",
            options=["[[1, 2], [3, 4]]", "[1, 2, 3, 4]", "SyntaxError", "A generator object"],
            correct_index=1, explanation="The * unpacking operator expands elements into a new flat list."
        ),
        QuizQuestion(
            id="py_i3", skill="Python", difficulty="Intermediate",
            question="What does `functools.wraps` do when building custom decorators?",
            options=[
                "Enforces type checking at runtime",
                "Preserves original function name, docstring, and module metadata",
                "Memoizes return values automatically",
                "Converts synchronous calls to asyncio tasks"
            ],
            correct_index=1, explanation="wraps copies metadata like __name__ and __doc__ from the wrapped function."
        ),
        QuizQuestion(
            id="py_i4", skill="Python", difficulty="Intermediate",
            question="Which method is called during object initialization before `__init__`?",
            options=["__call__", "__new__", "__repr__", "__enter__"],
            correct_index=1, explanation="__new__ is the constructor responsible for instantiating the class instance."
        ),
        QuizQuestion(
            id="py_i5", skill="Python", difficulty="Intermediate",
            question="How does `asyncio.gather()` handle concurrent coroutines?",
            options=[
                "Runs them in separate OS-level threads",
                "Runs them concurrently on the event loop and returns an ordered list of results",
                "Executes them sequentially with blocking I/O",
                "Spawns independent subprocesses for each task"
            ],
            correct_index=1, explanation="asyncio.gather schedules coroutines cooperatively on the single-threaded event loop."
        ),

        # Advanced (11-15)
        QuizQuestion(
            id="py_a1", skill="Python", difficulty="Advanced",
            question="What is a key difference between `__getattr__` and `__getattribute__`?",
            options=[
                "__getattr__ is called for every attribute access, while __getattribute__ only for missing ones",
                "__getattribute__ is called unconditionally for every attribute lookup, while __getattr__ is only fallback for missing attributes",
                "__getattr__ only works on class methods",
                "There is no difference in modern Python"
            ],
            correct_index=1, explanation="__getattribute__ intercepts all lookups; __getattr__ is only invoked if standard lookup raises AttributeError."
        ),
        QuizQuestion(
            id="py_a2", skill="Python", difficulty="Advanced",
            question="What memory optimization does `__slots__` provide in a class?",
            options=[
                "Compresses object bytecode in memory",
                "Replaces the default `__dict__` with a static descriptor array, reducing per-instance memory footprint",
                "Enables multithreaded shared heap allocation",
                "Caches method pointers in CPU L1 cache"
            ],
            correct_index=1, explanation="__slots__ eliminates the __dict__ and __weakref__ overhead per instance."
        ),
        QuizQuestion(
            id="py_a3", skill="Python", difficulty="Advanced",
            question="When using contextlib.contextmanager, what happens if an exception is raised inside the caller's with-block?",
            options=[
                "It is silently swallowed by default",
                "It is re-raised at the yield statement inside the generator",
                "It triggers a ProcessLookupError",
                "It aborts Python process termination"
            ],
            correct_index=1, explanation="The exception is injected into the generator at the yield point, allowing try/finally cleanups."
        ),
        QuizQuestion(
            id="py_a4", skill="Python", difficulty="Advanced",
            question="In Python's descriptor protocol, what constitutes a 'data descriptor'?",
            options=[
                "A descriptor defining only `__get__`",
                "A descriptor implementing both `__get__` and `__set__` (or `__delete__`)",
                "Any class inheriting from dataclass",
                "Any variable stored in globals()"
            ],
            correct_index=1, explanation="A data descriptor defines __set__ or __delete__, taking precedence over instance dictionary keys."
        ),
        QuizQuestion(
            id="py_a5", skill="Python", difficulty="Advanced",
            question="How does CPython's generational garbage collector handle cyclic references?",
            options=[
                "It relies exclusively on reference counters and cannot collect cycles",
                "It tracks container objects across 3 generations using doubly-linked lists and trial deletion",
                "It swaps cycle references into OS virtual memory pages",
                "It executes a full stop-the-world mark-and-sweep on every variable deletion"
            ],
            correct_index=1, explanation="CPython employs a tri-generational cyclic garbage collector detecting unreferenced isolated clusters."
        )
    ],

    "Docker": [
        QuizQuestion(
            id="dk_b1", skill="Docker", difficulty="Basic",
            question="Which file defines the build steps for a custom Docker image?",
            options=["Dockerfile", "docker-compose.yml", "Containerfile.json", "Imagefile"],
            correct_index=0, explanation="Dockerfile is the standard build specification file."
        ),
        QuizQuestion(
            id="dk_b2", skill="Docker", difficulty="Basic",
            question="What command lists currently running containers?",
            options=["docker ps", "docker images", "docker run", "docker inspect"],
            correct_index=0, explanation="docker ps lists active running containers."
        ),
        QuizQuestion(
            id="dk_b3", skill="Docker", difficulty="Basic",
            question="Which command runs a container in detached background mode?",
            options=["docker run -d", "docker run -b", "docker run --async", "docker run -f"],
            correct_index=0, explanation="-d stands for detached mode."
        ),
        QuizQuestion(
            id="dk_b4", skill="Docker", difficulty="Basic",
            question="What is the purpose of `.dockerignore`?",
            options=["Exclude files from being sent to Docker daemon build context", "Prevent containers from stopping", "Ignore CVE security vulnerabilities", "Delete images automatically"],
            correct_index=0, explanation=".dockerignore keeps large folders like node_modules out of the build context."
        ),
        QuizQuestion(
            id="dk_b5", skill="Docker", difficulty="Basic",
            question="What instruction specifies the default executable command in a Dockerfile?",
            options=["ENTRYPOINT / CMD", "RUN", "BUILD", "START"],
            correct_index=0, explanation="ENTRYPOINT and CMD dictate the process executed when the container starts."
        ),

        QuizQuestion(
            id="dk_i1", skill="Docker", difficulty="Intermediate",
            question="What is the primary benefit of multi-stage Docker builds?",
            options=["Faster network downloads only", "Drastically smaller final production image size by separating build tools from runtime", "Automatic Kubernetes pod scaling", "Disabling root user privileges by default"],
            correct_index=1, explanation="Multi-stage builds leave compiler SDKs and build artifacts in earlier throwaway stages."
        ),
        QuizQuestion(
            id="dk_i2", skill="Docker", difficulty="Intermediate",
            question="What is the difference between `CMD` and `ENTRYPOINT` in a Dockerfile?",
            options=[
                "ENTRYPOINT defines the executable, while CMD provides default parameters that can be overridden",
                "CMD is mandatory; ENTRYPOINT is deprecated",
                "CMD runs at image build time; ENTRYPOINT at run time",
                "There is no difference in syntax or behavior"
            ],
            correct_index=0, explanation="ENTRYPOINT sets the constant executable; CMD sets default args that cli parameters override."
        ),
        QuizQuestion(
            id="dk_i3", skill="Docker", difficulty="Intermediate",
            question="How should sensitive credentials (e.g. AWS keys) be provided during a docker build?",
            options=["In plain RUN echo in Dockerfile", "Using Docker BuildKit --secret mount flags", "As plain ENV instructions in Dockerfile", "Committed inside the Git repository"],
            correct_index=1, explanation="BuildKit secret mounts prevent credentials from leaking into cached image layers."
        ),
        QuizQuestion(
            id="dk_i4", skill="Docker", difficulty="Intermediate",
            question="What is the default network driver for standalone containers in Docker?",
            options=["host", "bridge", "overlay", "macvlan"],
            correct_index=1, explanation="bridge is the default network mode for individual containers."
        ),
        QuizQuestion(
            id="dk_i5", skill="Docker", difficulty="Intermediate",
            question="Why should you avoid running containers as the `root` user in production?",
            options=["It uses more disk RAM", "Container breakout vulnerabilities could grant host root privileges", "Docker images fail to build as root", "It breaks TLS certificates"],
            correct_index=1, explanation="Running as non-root mitigates container escape and privilege escalation exploits."
        ),

        QuizQuestion(
            id="dk_a1", skill="Docker", difficulty="Advanced",
            question="Which Linux kernel mechanisms form the fundamental isolation foundation of Docker containers?",
            options=["Namespaces (PID, Mount, Net) and Control Groups (cgroups)", "Chroot and X11 forwarding", "SELinux and Systemd units only", "KVM hypervisor virtualization"],
            correct_index=0, explanation="Namespaces isolate process views; cgroups enforce resource quotas (CPU/RAM)."
        ),
        QuizQuestion(
            id="dk_a2", skill="Docker", difficulty="Advanced",
            question="What happens when an application in a container exceeds its cgroup memory limit?",
            options=["The container receives a SIGTERM warning", "The Linux OOM (Out Of Memory) killer sends SIGKILL to the container process", "Docker expands host swap space automatically", "The process slows down via throttling without dying"],
            correct_index=1, explanation="Exceeding hard memory limits triggers the kernel OOM killer, killing the process with exit code 137."
        ),
        QuizQuestion(
            id="dk_a3", skill="Docker", difficulty="Advanced",
            question="How does Docker's OverlayFS storage driver manage writes to files originating from lower read-only image layers?",
            options=["Direct in-place modification of read-only image layers", "Copy-on-write (CoW) duplicating the file into the upper writable container layer", "Shared lock on virtual inode", "Immediate kernel core dump"],
            correct_index=1, explanation="OverlayFS uses Copy-on-Write, copying modified files to the writable top layer."
        ),
        QuizQuestion(
            id="dk_a4", skill="Docker", difficulty="Advanced",
            question="What does dropping the `CAP_NET_RAW` Linux capability prevent inside a container?",
            options=["DNS resolution", "Crafting raw packets and ARP spoofing attacks", "Binding to port 80", "Connecting to external TCP sockets"],
            correct_index=1, explanation="Dropping CAP_NET_RAW blocks raw packet forging and internal network sniffing."
        ),
        QuizQuestion(
            id="dk_a5", skill="Docker", difficulty="Advanced",
            question="In Docker daemon rootless mode, how are unprivileged ports mapped to host interfaces?",
            options=["Using root setuid binaries", "Via RootlessKit and user namespaces with slirp4netns / VPNKit", "Direct iptables kernel bypass", "Raw socket broadcasting"],
            correct_index=1, explanation="RootlessKit creates user namespace network taps using user-mode network stacks."
        )
    ]
}

class QuestionBankEngine:
    def get_questions_for_skill(self, skill: str) -> List[QuizQuestion]:
        # Exact skill match only: a Python quiz must never grade a Java (or any other) claim
        return SAMPLE_QUIZZES.get(normalize_skill(skill), [])

    def public_questions(self, skill: str) -> List[PublicQuizQuestion]:
        return [PublicQuizQuestion(**q.model_dump(include={"id", "skill", "difficulty", "question", "options"}))
                for q in self.get_questions_for_skill(skill)]

    def evaluate_quiz(self, skill: str, answers: Dict[str, int]) -> QuizResult:
        questions = self.get_questions_for_skill(skill)
        total = len(questions)
        correct = 0

        for q in questions:
            user_choice = answers.get(q.id)
            if user_choice is not None and user_choice == q.correct_index:
                correct += 1

        pct = round((correct / max(1, total)) * 100.0, 1)
        grade = DeterministicScoringEngine.grade_from_percentage(pct)
        grade_weight = GRADE_WEIGHTS[grade]

        return QuizResult(
            skill=skill,
            total_questions=total,
            correct_count=correct,
            percentage=pct,
            grade=grade,
            grade_weight=grade_weight,
            review=[
                QuizReviewItem(id=q.id, chosen_index=answers.get(q.id), correct_index=q.correct_index, explanation=q.explanation)
                for q in questions
            ]
        )
