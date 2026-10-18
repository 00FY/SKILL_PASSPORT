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

    "FastAPI": [
        # Basic (1-5)
        QuizQuestion(
            id="fa_b1", skill="FastAPI", difficulty="Basic",
            question="What library does FastAPI rely on for data validation and serialization?",
            options=["Marshmallow", "Pydantic", "Cerberus", "Schema"],
            correct_index=1, explanation="FastAPI is built on top of Pydantic for data parsing and schema validation."
        ),
        QuizQuestion(
            id="fa_b2", skill="FastAPI", difficulty="Basic",
            question="Which ASGI server is standard for deploying FastAPI applications?",
            options=["Gunicorn (sync)", "Uvicorn", "Waitress", "uWSGI"],
            correct_index=1, explanation="Uvicorn is a lightning-fast ASGI server implementation based on uvloop and httptools."
        ),
        QuizQuestion(
            id="fa_b3", skill="FastAPI", difficulty="Basic",
            question="Which decorator registers an HTTP POST route handler in FastAPI?",
            options=["@app.route(method='POST')", "@app.post()", "@app.create()", "@api.handle_post()"],
            correct_index=1, explanation="FastAPI uses intuitive HTTP method decorators like @app.get(), @app.post(), etc."
        ),
        QuizQuestion(
            id="fa_b4", skill="FastAPI", difficulty="Basic",
            question="What URL path serves interactive Swagger UI documentation by default?",
            options=["/api/v1/swagger", "/docs", "/openapi.html", "/swagger-ui"],
            correct_index=1, explanation="FastAPI automatically exposes interactive Swagger UI at the '/docs' endpoint."
        ),
        QuizQuestion(
            id="fa_b5", skill="FastAPI", difficulty="Basic",
            question="What HTTP status code does FastAPI automatically return when payload validation fails?",
            options=["400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error", "403 Forbidden"],
            correct_index=1, explanation="FastAPI adheres to RFC standards and returns 422 Unprocessable Entity for schema validation failures."
        ),
        # Intermediate (6-10)
        QuizQuestion(
            id="fa_i1", skill="FastAPI", difficulty="Intermediate",
            question="How does FastAPI declare dependency injection across path operations?",
            options=["Using Inject() in decorators", "Using Depends() as a default parameter value", "Using global ServiceLocator", "Through metaclass inheritance"],
            correct_index=1, explanation="Depends() is FastAPI's clean dependency injection system used for auth, database sessions, and logic reuse."
        ),
        QuizQuestion(
            id="fa_i2", skill="FastAPI", difficulty="Intermediate",
            question="How do you split route definitions into clean modular files?",
            options=["Importing routes directly into app.py", "Using APIRouter and app.include_router()", "Registering Blueprints", "Using sub-FastAPI instances only"],
            correct_index=1, explanation="APIRouter allows structuring routes into modular controllers and attaching them with app.include_router()."
        ),
        QuizQuestion(
            id="fa_i3", skill="FastAPI", difficulty="Intermediate",
            question="How do you execute background tasks after sending the response to the client?",
            options=["Spawning multiprocessing.Process", "Declaring a BackgroundTasks parameter in the path operation", "Calling threading.Thread.start() directly", "Using raw Celery delay() only"],
            correct_index=1, explanation="FastAPI provides a built-in BackgroundTasks class that runs tasks after returning the response."
        ),
        QuizQuestion(
            id="fa_i4", skill="FastAPI", difficulty="Intermediate",
            question="What is the benefit of defining route handlers with `async def` in FastAPI?",
            options=["Computes mathematical loops faster", "Enables non-blocking I/O operations directly on the ASGI event loop", "Forces multi-core parallelism", "Disables memory garbage collection"],
            correct_index=1, explanation="async def allows coroutines to yield control during network/database I/O without blocking other requests."
        ),
        QuizQuestion(
            id="fa_i5", skill="FastAPI", difficulty="Intermediate",
            question="How can you add custom validation rules to URL query parameters?",
            options=["Using Query() with constraints like min_length, regex, and ge", "Writing custom regex inside the handler body", "Using @validate_query decorator", "Query parameters cannot be validated"],
            correct_index=0, explanation="fastapi.Query provides built-in validation attributes like min_length, max_length, regex, and bounds."
        ),
        # Advanced (11-15)
        QuizQuestion(
            id="fa_a1", skill="FastAPI", difficulty="Advanced",
            question="How do modern FastAPI versions (0.93+) recommend handling application startup and shutdown events?",
            options=["Using @app.on_event('startup') only", "Using an async contextmanager passed to the lifespan parameter of FastAPI()", "Writing custom OS signal handlers", "Using a __del__ class destructor"],
            correct_index=1, explanation="Lifespan context managers replace legacy on_event handlers and cleanly manage setup and teardown."
        ),
        QuizQuestion(
            id="fa_a2", skill="FastAPI", difficulty="Advanced",
            question="How does FastAPI execute synchronous path operations defined with regular `def`?",
            options=["Blocks the main event loop until finished", "Executes them in an external worker threadpool via AnyIO", "Automatically converts them to coroutines using bytecode translation", "Rejects them with a RuntimeError"],
            correct_index=1, explanation="FastAPI runs synchronous def handlers in a threadpool to prevent blocking the event loop for async operations."
        ),
        QuizQuestion(
            id="fa_a3", skill="FastAPI", difficulty="Advanced",
            question="In FastAPI dependency resolution, what does `use_cache=True` (the default) ensure?",
            options=["Caches results in Redis across client requests", "Executes the dependency once per request and shares the return value across all sub-dependencies", "Caches response JSON in browser memory", "Stores function bytecode in RAM"],
            correct_index=1, explanation="Per-request dependency caching guarantees identical dependency instances (like db sessions) are shared within one request."
        ),
        QuizQuestion(
            id="fa_a4", skill="FastAPI", difficulty="Advanced",
            question="How should global HTTP middleware be registered to modify requests and responses?",
            options=["@app.middleware('http') with an async def(request, call_next) function", "Subclassing HTTPHandler in main.py", "Registering WSGI interceptor", "Overriding app.request()"],
            correct_index=0, explanation="HTTP middleware functions receive the incoming request and call_next to process and wrap the response."
        ),
        QuizQuestion(
            id="fa_a5", skill="FastAPI", difficulty="Advanced",
            question="What is the purpose of `HTTPException` vs raw Python `Exception` in route handlers?",
            options=["HTTPException automatically serializes to structured JSON with status_code and detail headers", "Raw exceptions are faster", "HTTPException kills the server process", "There is no difference"],
            correct_index=0, explanation="FastAPI's HTTPException is caught by default exception handlers and converted to standard JSON error responses."
        )
    ],

    "Docker": [
        # Basic (1-5)
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
        # Intermediate (6-10)
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
        # Advanced (11-15)
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
    ],

    "JavaScript": [
        QuizQuestion(id="js_b1", skill="JavaScript", difficulty="Basic", question="Which keyword declares a block-scoped variable that cannot be reassigned?", options=["var", "let", "const", "def"], correct_index=2, explanation="const declares an immutable block-scoped binding."),
        QuizQuestion(id="js_b2", skill="JavaScript", difficulty="Basic", question="What will `typeof NaN` return in JavaScript?", options=["'number'", "'nan'", "'undefined'", "'object'"], correct_index=0, explanation="In JavaScript specification, NaN is of type number."),
        QuizQuestion(id="js_b3", skill="JavaScript", difficulty="Basic", question="What is the result of `'5' + 3` vs `'5' - 3`?", options=["'53' and 2", "8 and 2", "'53' and '5-3'", "TypeError"], correct_index=0, explanation="+ coerces to string concatenation; - coerces to numeric subtraction."),
        QuizQuestion(id="js_b4", skill="JavaScript", difficulty="Basic", question="Which method creates a new array populated with the results of calling a function on every element?", options=["forEach()", "map()", "filter()", "reduce()"], correct_index=1, explanation="map() returns a new transformed array."),
        QuizQuestion(id="js_b5", skill="JavaScript", difficulty="Basic", question="What is the difference between `==` and `===`?", options=["=== checks type and value without coercion", "== checks strict memory reference", "=== is deprecated in ES6", "There is no difference"], correct_index=0, explanation="=== performs strict equality without type coercion."),
        QuizQuestion(id="js_i1", skill="JavaScript", difficulty="Intermediate", question="What is a closure in JavaScript?", options=["A method to terminate event loops", "A function bundled together with references to its surrounding lexical state", "A private class property syntax", "An immediately invoked arrow function"], correct_index=1, explanation="Closures allow inner functions to access outer scope variables even after outer execution completes."),
        QuizQuestion(id="js_i2", skill="JavaScript", difficulty="Intermediate", question="How does JavaScript's event loop prioritize Microtasks vs Macrotasks?", options=["Macrotasks run before microtasks", "All microtasks in the queue are executed immediately after current execution and before the next macrotask", "Both queues execute in round-robin order", "Microtasks only run during garbage collection"], correct_index=1, explanation="Microtasks (Promise callbacks, queueMicrotask) run to completion before processing the next macrotask (setTimeout)."),
        QuizQuestion(id="js_i3", skill="JavaScript", difficulty="Intermediate", question="What does `Promise.all()` do if any one promise in the iterable rejects?", options=["Waits for all others before failing", "Immediately rejects with the error of the first rejected promise", "Ignores the error and resolves remaining", "Returns an array of errors"], correct_index=1, explanation="Promise.all is fail-fast: if one rejects, the entire bundle rejects immediately."),
        QuizQuestion(id="js_i4", skill="JavaScript", difficulty="Intermediate", question="What is the difference between `null` and `undefined`?", options=["null is an explicit assignment of 'no value'; undefined means a variable has been declared but not assigned", "undefined is an object; null is a primitive", "null is automatically assigned to uninitialized variables", "They are identical in memory"], correct_index=0, explanation="undefined is default unassigned state; null represents intentional absence of object value."),
        QuizQuestion(id="js_i5", skill="JavaScript", difficulty="Intermediate", question="What will `console.log(this)` output inside a regular function in non-strict mode in a browser?", options=["undefined", "window", "null", "document"], correct_index=1, explanation="In non-strict mode, unbonded functions resolve 'this' to the global window object."),
        QuizQuestion(id="js_a1", skill="JavaScript", difficulty="Advanced", question="Why does `WeakMap` only accept objects as keys?", options=["To allow garbage collection of keys when no other references exist", "Because strings cannot be hashed in V8", "To enforce TypeScript compilation", "WeakMap supports primitives in ES2023"], correct_index=0, explanation="WeakMap holds weak references to key objects, allowing them to be garbage collected."),
        QuizQuestion(id="js_a2", skill="JavaScript", difficulty="Advanced", question="What happens during prototype chain lookup when an attribute is not found on an object?", options=["Raises ReferenceError", "Traverses `__proto__` up to `Object.prototype`, returning `undefined` if not found", "Re-evaluates the constructor function", "Throws TypeError"], correct_index=1, explanation="Prototypal inheritance traverses prototype references until hitting Object.prototype then null."),
        QuizQuestion(id="js_a3", skill="JavaScript", difficulty="Advanced", question="What does the `Symbol.iterator` property define on an object?", options=["Serialization formatting for JSON.stringify", "The default iterator method consumed by `for...of` and spread syntax", "Internal memory pointer for garbage collector", "A unique identifier for Map keys"], correct_index=1, explanation="Symbol.iterator specifies the iterator generator function for iterable protocols."),
        QuizQuestion(id="js_a4", skill="JavaScript", difficulty="Advanced", question="What is the key difference between debouncing and throttling a function?", options=["Debounce runs periodically; throttle waits until caller stops", "Debounce groups multiple calls into one after a delay of silence; throttle limits execution to once per fixed time interval", "They are identical utility algorithms", "Throttle only works on scroll events"], correct_index=1, explanation="Debouncing delays until quiet; throttling rate-limits execution to at most once per time window."),
        QuizQuestion(id="js_a5", skill="JavaScript", difficulty="Advanced", question="In JavaScript V8 engine, what are 'Hidden Classes' (Shapes) used for?", options=["Encrypting private class fields", "Fast property access optimization bypassing hash table lookups via inline caching", "Compressing AST size", "Implementing WebAssembly bridges"], correct_index=1, explanation="V8 uses hidden classes (Shapes) to enable fast inline caching of object properties.")
    ],

    "TypeScript": [
        QuizQuestion(id="ts_b1", skill="TypeScript", difficulty="Basic", question="Which operator allows declaring a variable that can be either string or number?", options=["string & number", "string | number", "string or number", "Union<string, number>"], correct_index=1, explanation="| denotes a union type in TypeScript."),
        QuizQuestion(id="ts_b2", skill="TypeScript", difficulty="Basic", question="What does the `unknown` type represent compared to `any`?", options=["Type-safe counterpart of any: cannot be operated on without type narrowing", "Identical to any in every aspect", "Represents values that never return", "Can only hold undefined"], correct_index=0, explanation="unknown forces type checking/narrowing before any property access or operations."),
        QuizQuestion(id="ts_b3", skill="TypeScript", difficulty="Basic", question="How do you define an optional property in a TypeScript interface?", options=["name: string?", "name?: string", "optional name: string", "name: Optional<string>"], correct_index=1, explanation="? suffix declares an optional property."),
        QuizQuestion(id="ts_b4", skill="TypeScript", difficulty="Basic", question="What compiler command generates JavaScript from TypeScript files?", options=["tsc", "ts-run", "ts-compile", "npm build-ts"], correct_index=0, explanation="tsc (TypeScript Compiler) compiles .ts files into standard .js."),
        QuizQuestion(id="ts_b5", skill="TypeScript", difficulty="Basic", question="What type does a function return if it throws an error and never reaches completion?", options=["void", "null", "never", "undefined"], correct_index=2, explanation="never represents the return type for functions that never return normally (e.g. infinite loop or throw)."),
        QuizQuestion(id="ts_i1", skill="TypeScript", difficulty="Intermediate", question="What is a Discriminated Union in TypeScript?", options=["A union of types with a shared literal tag property enabling exhaustive type narrowing", "A union of interfaces that cannot be combined", "A deprecated TypeScript syntax", "An intersection type of multiple primitives"], correct_index=0, explanation="Discriminated unions use a common literal field (like `type: 'success' | 'error'`) for safe switch/case narrowing."),
        QuizQuestion(id="ts_i2", skill="TypeScript", difficulty="Intermediate", question="What utility type constructs a type with all properties of T set to optional?", options=["Omit<T>", "Partial<T>", "Pick<T>", "Readonly<T>"], correct_index=1, explanation="Partial<T> transforms all fields of T into optional fields."),
        QuizQuestion(id="ts_i3", skill="TypeScript", difficulty="Intermediate", question="What is the difference between `interface` and `type` alias?", options=["Interfaces can be merged through declaration merging; types cannot be reopened", "Types cannot represent object shapes", "Interfaces cannot use generics", "There are no differences in modern TypeScript"], correct_index=0, explanation="Declaration merging allows multiple interface definitions with the same name to merge."),
        QuizQuestion(id="ts_i4", skill="TypeScript", difficulty="Intermediate", question="What does the `keyof` operator return?", options=["Array of runtime object keys", "A union of string and numeric literal types representing property names of a type", "The length of an interface", "A boolean flag indicating key presence"], correct_index=1, explanation="keyof produces a union type of all known keys on a type."),
        QuizQuestion(id="ts_i5", skill="TypeScript", difficulty="Intermediate", question="What does `as const` assertion do in TypeScript?", options=["Compiles to const in JavaScript runtime", "Narrows primitive types to their exact literal values and marks all object properties readonly", "Prevents garbage collection", "Imports constants from external modules"], correct_index=1, explanation="const assertions lock types to exact literals and deep readonly structures."),
        QuizQuestion(id="ts_a1", skill="TypeScript", difficulty="Advanced", question="What does `infer` keyword do inside conditional types?", options=["Forces runtime type inference", "Introduces a type variable to be deduced within the true branch of a conditional type", "Casts any value to unknown", "Suppresses compiler errors"], correct_index=1, explanation="infer R allows extracting component types (like Promise return types: `T extends Promise<infer R> ? R : T`)."),
        QuizQuestion(id="ts_a2", skill="TypeScript", difficulty="Advanced", question="How does distributive conditional typing behave over naked type parameters in unions?", options=["Distributes the conditional across each union member individually: `(A | B) extends T ? X : Y` becomes `(A extends T ? X : Y) | (B extends T ? X : Y)`", "Evaluates the union as an inseparable block", "Throws a compiler error", "Always resolves to never"], correct_index=0, explanation="Naked type parameters distribute over union members automatically in conditional types."),
        QuizQuestion(id="ts_a3", skill="TypeScript", difficulty="Advanced", question="What is the purpose of template literal types in TypeScript 4.1+?", options=["Evaluating JavaScript string templates at runtime", "Building new string types via template literal syntax like `type Event = `on${Capitalize<Action>}`;`", "Injecting HTML strings into React components", "Replacing standard enum definitions"], correct_index=1, explanation="Template literal types enable type-level string manipulation and pattern matching."),
        QuizQuestion(id="ts_a4", skill="TypeScript", difficulty="Advanced", question="What does `satisfies` operator do in TypeScript 4.9+?", options=["Validates that an expression matches a type without widening its inferred type", "Overwrites object prototypes at runtime", "Replaces the `as` casting operator completely", "Enforces runtime schema validation"], correct_index=0, explanation="satisfies validates type conformance while preserving the most specific literal inference."),
        QuizQuestion(id="ts_a5", skill="TypeScript", difficulty="Advanced", question="What is structural subtyping ('duck typing') in TypeScript?", options=["Types are compatible based on their member shapes and properties rather than explicit nominal inheritance", "All classes must inherit from a common base Duck class", "Only duck-typed objects can be passed to functions", "A runtime method lookup mechanism"], correct_index=0, explanation="TypeScript uses structural typing: if two types share compatible members, they are assignable regardless of nominal declarations.")
    ],

    "React": [
        QuizQuestion(id="re_b1", skill="React", difficulty="Basic", question="Which Hook manages local state in a functional component?", options=["useEffect", "useState", "useContext", "useReducer"], correct_index=1, explanation="useState declares local state variables in React components."),
        QuizQuestion(id="re_b2", skill="React", difficulty="Basic", question="Why must JSX elements inside array maps have a unique `key` prop?", options=["To style them with CSS", "To help React identify which items have changed, added, or removed during reconciliation", "To register event listeners automatically", "It is optional and purely cosmetic"], correct_index=1, explanation="Keys provide stable identity across renders so React avoids unnecessary DOM recreations."),
        QuizQuestion(id="re_b3", skill="React", difficulty="Basic", question="What does JSX stand for in React?", options=["JavaScript XML", "JSON Schema Extension", "Java Syntax X", "JavaScript Xenon"], correct_index=0, explanation="JSX stands for JavaScript XML, allowing HTML-like syntax inside JavaScript."),
        QuizQuestion(id="re_b4", skill="React", difficulty="Basic", question="When does a `useEffect` with an empty dependency array `[]` run?", options=["On every single render", "Only once after initial mount", "Before every state mutation", "Never"], correct_index=1, explanation="An empty dependency array instructs React to execute the effect only once after initial mount."),
        QuizQuestion(id="re_b5", skill="React", difficulty="Basic", question="What is the primary rule regarding Hooks execution in React components?", options=["Call Hooks anywhere inside loops and conditions", "Only call Hooks at the top level of function components or custom Hooks", "Hooks can only be called inside class methods", "Hooks must be imported dynamically"], correct_index=1, explanation="Hooks must be called unconditionally at top level to maintain consistent call order."),
        QuizQuestion(id="re_i1", skill="React", difficulty="Intermediate", question="What is the purpose of `useCallback` in React?", options=["Memoize an expensive calculation result", "Memoize a function reference between renders to prevent unnecessary child re-renders", "Create asynchronous callbacks", "Bind this context in arrow functions"], correct_index=1, explanation="useCallback caches a function definition between renders unless dependencies change."),
        QuizQuestion(id="re_i2", skill="React", difficulty="Intermediate", question="What is the difference between `useMemo` and `useCallback`?", options=["useMemo caches the result of calling a function; useCallback caches the function instance itself", "useMemo is asynchronous; useCallback is synchronous", "useCallback is deprecated in React 18", "They are aliases for the same Hook"], correct_index=0, explanation="useMemo returns a memoized value; useCallback returns a memoized callback function."),
        QuizQuestion(id="re_i3", skill="React", difficulty="Intermediate", question="How does React handle state updates inside event handlers in React 18+?", options=["Executes each update synchronously one by one", "Automatically batches multiple state updates into a single re-render", "Disables rendering until next macro-task", "Spawns Web Workers"], correct_index=1, explanation="React 18 introduced automatic batching for all updates (promises, timeouts, native events)."),
        QuizQuestion(id="re_i4", skill="React", difficulty="Intermediate", question="Why should you never mutate state objects directly in React?", options=["Direct mutation does not trigger re-renders because React checks reference equality (Object.is)", "It crashes the browser V8 engine", "Direct mutation converts objects to strings", "React automatically clones objects anyway"], correct_index=0, explanation="React relies on immutable updates and reference changes to detect when to re-render."),
        QuizQuestion(id="re_i5", skill="React", difficulty="Intermediate", question="What does `useRef` provide beyond accessing DOM nodes?", options=["A persistent mutable value that does NOT trigger a re-render when modified", "A cached memoized calculation", "Global application state management", "Automatic two-way data binding"], correct_index=0, explanation="useRef returns a mutable ref object whose .current property persists without causing re-renders."),
        QuizQuestion(id="re_a1", skill="React", difficulty="Advanced", question="How does React's Fiber architecture enable Concurrent Mode?", options=["Splits rendering work into small incremental units that can be paused, aborted, or prioritized", "Executes rendering inside multiple OS processes", "Replaces the DOM with WebGL canvas rendering", "Compiles React components to C++ WebAssembly"], correct_index=0, explanation="Fiber represents a virtual stack frame enabling cooperative scheduling and interruptible rendering."),
        QuizQuestion(id="re_a2", skill="React", difficulty="Advanced", question="What is the purpose of `useTransition` in React 18?", options=["CSS animations between pages", "Marks state updates as non-urgent transitions, keeping the UI responsive during heavy renders", "Handles router redirects", "Transitions class components to functional components"], correct_index=1, explanation="useTransition lets you mark updates as transitions to keep the interface interactive."),
        QuizQuestion(id="re_a3", skill="React", difficulty="Advanced", question="What does React Suspense do when a component suspends?", options=["Throws a caught Promise, rendering fallback UI until the Promise resolves", "Freezes the browser event loop", "Terminates the component subtree permanently", "Displays an alert popup dialog"], correct_index=0, explanation="Suspense intercepts thrown promises from data fetching or lazy loading to show fallback indicators."),
        QuizQuestion(id="re_a4", skill="React", difficulty="Advanced", question="In custom Hook development, what does `useId` guarantee?", options=["Generates unique, stable IDs across client and server to prevent SSR hydration mismatches", "Returns random UUIDs on every render", "Generates cryptographic session tokens", "Acts as a database primary key generator"], correct_index=0, explanation="useId produces stable, unique IDs that match seamlessly across SSR and client hydration."),
        QuizQuestion(id="re_a5", skill="React", difficulty="Advanced", question="What happens during Server Component (RSC) rendering vs Client Components in Next.js/React?", options=["Server Components execute exclusively on the server, producing zero client bundle JavaScript", "Server Components run in browser Web Workers", "Server Components cannot accept props", "Client Components cannot use CSS"], correct_index=0, explanation="React Server Components render on the server and ship no JS bundle to the client, reducing download size.")
    ],

    "SQL": [
        QuizQuestion(id="sql_b1", skill="SQL", difficulty="Basic", question="Which SQL clause filters rows before aggregation?", options=["WHERE", "HAVING", "GROUP BY", "ORDER BY"], correct_index=0, explanation="WHERE filters individual rows before grouping/aggregation; HAVING filters after."),
        QuizQuestion(id="sql_b2", skill="SQL", difficulty="Basic", question="Which JOIN returns all rows from the left table and matched rows from the right table?", options=["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"], correct_index=1, explanation="LEFT JOIN returns all rows from the left table, with NULLs for unmatched right records."),
        QuizQuestion(id="sql_b3", skill="SQL", difficulty="Basic", question="What keyword removes duplicate rows from a query result set?", options=["UNIQUE", "DISTINCT", "DIFFERENT", "FILTER"], correct_index=1, explanation="SELECT DISTINCT eliminates duplicate rows from results."),
        QuizQuestion(id="sql_b4", skill="SQL", difficulty="Basic", question="Which command permanently removes a table and its structure from a database?", options=["DELETE TABLE", "DROP TABLE", "TRUNCATE TABLE", "REMOVE TABLE"], correct_index=1, explanation="DROP TABLE removes the entire table definition and data from the catalog."),
        QuizQuestion(id="sql_b5", skill="SQL", difficulty="Basic", question="What constraint uniquely identifies each record in a database table?", options=["FOREIGN KEY", "PRIMARY KEY", "CHECK", "NOT NULL"], correct_index=1, explanation="A PRIMARY KEY uniquely identifies every record and enforces non-null uniqueness."),
        QuizQuestion(id="sql_i1", skill="SQL", difficulty="Intermediate", question="What is the difference between `TRUNCATE` and `DELETE`?", options=["TRUNCATE is DDL, resets high-water marks/identity and cannot be rolled back in some engines; DELETE is DML row-by-row", "DELETE drops table columns", "TRUNCATE allows WHERE clauses", "They are identical in performance"], correct_index=0, explanation="TRUNCATE deallocates data pages rapidly; DELETE logs row deletions individually."),
        QuizQuestion(id="sql_i2", skill="SQL", difficulty="Intermediate", question="What does ACID stand for in database transaction theory?", options=["Atomicity, Consistency, Isolation, Durability", "Asynchronous, Concurrent, Indexed, Distributed", "Action, Constraint, Integrity, Dependency", "Automated, Checked, Isolated, Durable"], correct_index=0, explanation="ACID represents the 4 key properties guaranteeing transaction reliability."),
        QuizQuestion(id="sql_i3", skill="SQL", difficulty="Intermediate", question="What is the primary purpose of a database Index (e.g. B-Tree)?", options=["Enforce table foreign keys only", "Speed up data retrieval operations without scanning every row in the table", "Compress column data on disk", "Encrypt confidential columns"], correct_index=1, explanation="Indexes provide fast log-time lookup paths to rows, avoiding sequential full table scans."),
        QuizQuestion(id="sql_i4", skill="SQL", difficulty="Intermediate", question="What is the difference between `UNION` and `UNION ALL`?", options=["UNION removes duplicate rows; UNION ALL retains all rows including duplicates and is faster", "UNION ALL is sorted; UNION is unsorted", "UNION works across different databases; UNION ALL is local", "There is no difference in output"], correct_index=0, explanation="UNION performs distinct sorting to discard duplicates; UNION ALL concatenates directly."),
        QuizQuestion(id="sql_i5", skill="SQL", difficulty="Intermediate", question="What function assigns a sequential integer rank to rows within a partition without gaps?", options=["RANK()", "DENSE_RANK()", "ROW_NUMBER()", "NTILE()"], correct_index=1, explanation="DENSE_RANK() assigns sequential ranks without gaps when values tie."),
        QuizQuestion(id="sql_a1", skill="SQL", difficulty="Advanced", question="What anomaly does the 'Serializable' transaction isolation level prevent that 'Repeatable Read' permits in some engines?", options=["Dirty Reads", "Non-Repeatable Reads", "Phantom Reads / Write Skew", "Lost Updates"], correct_index=2, explanation="Serializable eliminates phantom reads and write skew anomalies via strict two-phase locking or SSI."),
        QuizQuestion(id="sql_a2", skill="SQL", difficulty="Advanced", question="In PostgreSQL, what is the consequence of table updates under MVCC (Multi-Version Concurrency Control)?", options=["In-place overwrite of raw bytes", "A new tuple version is written and the old tuple is marked dead, necessitating VACUUM to reclaim space", "Table locks are held until transaction commits", "Data pages are copied to tempdb"], correct_index=1, explanation="PostgreSQL MVCC writes new row versions (dead tuples) requiring VACUUM cleanup."),
        QuizQuestion(id="sql_a3", skill="SQL", difficulty="Advanced", question="What does a covering index (INDEX ... INCLUDE) achieve in query optimization?", options=["Allows the database engine to satisfy the query entirely from index leaf pages (Index-Only Scan) without touching heap tables", "Covers all tables in the database schema", "Compresses index size on disk", "Enforces foreign key relationships"], correct_index=0, explanation="Covering indexes include payload columns in index leaf nodes to enable Index-Only Scans."),
        QuizQuestion(id="sql_a4", skill="SQL", difficulty="Advanced", question="What is the difference between Common Table Expressions (WITH) and Temporary Tables?", options=["CTEs exist only for query execution scope; Temp Tables are physical session-scoped tables that can be indexed", "CTEs write to disk; Temp tables are in-memory only", "CTEs cannot be recursive", "Temp tables cannot be joined"], correct_index=0, explanation="CTEs provide clean inline query readability; Temp tables persist for the session and support statistics/indexes."),
        QuizQuestion(id="sql_a5", skill="SQL", difficulty="Advanced", question="What does database normalization to Third Normal Form (3NF) require?", options=["Table is in 2NF and has no transitive functional dependencies between non-key attributes", "Table has no primary key", "Every column must be encrypted", "Table must be denormalized for OLAP"], correct_index=0, explanation="3NF requires that every non-key column depends directly on the key, the whole key, and nothing but the key.")
    ],

    "Git": [
        QuizQuestion(id="git_b1", skill="Git", difficulty="Basic", question="Which command checks the current status of the working tree and staging area?", options=["git status", "git log", "git diff", "git check"], correct_index=0, explanation="git status displays modified, staged, and untracked files."),
        QuizQuestion(id="git_b2", skill="Git", difficulty="Basic", question="What command adds modified files to the staging index?", options=["git add <file>", "git stage-now <file>", "git commit <file>", "git push <file>"], correct_index=0, explanation="git add stages files for the next commit."),
        QuizQuestion(id="git_b3", skill="Git", difficulty="Basic", question="Which command creates a new branch and switches to it in modern Git?", options=["git branch -c <name>", "git switch -c <name>", "git checkout --new <name>", "git fork <name>"], correct_index=1, explanation="git switch -c <name> creates and checks out a new branch."),
        QuizQuestion(id="git_b4", skill="Git", difficulty="Basic", question="What does `git pull` do under the hood?", options=["git push and git commit", "git fetch followed by git merge (or rebase)", "git clone and git reset", "git checkout origin/main"], correct_index=1, explanation="git pull fetches remote commits and merges them into the current branch."),
        QuizQuestion(id="git_b5", skill="Git", difficulty="Basic", question="Which command displays line-by-line authorship history of a file?", options=["git who", "git blame", "git history", "git track"], correct_index=1, explanation="git blame shows the commit, author, and date for every line in a file."),
        QuizQuestion(id="git_i1", skill="Git", difficulty="Intermediate", question="What is the difference between `git merge` and `git rebase`?", options=["Merge preserves non-linear branch topology with a merge commit; rebase replays commits linearly on top of the base branch", "Rebase deletes commit history permanently", "Merge is local only; rebase is remote only", "There is no difference in history"], correct_index=0, explanation="Rebase rewrites commit hashes into a linear history; merge creates explicit branch junction commits."),
        QuizQuestion(id="git_i2", skill="Git", difficulty="Intermediate", question="What is a 'Detached HEAD' state in Git?", options=["HEAD points directly to a specific commit hash rather than a named branch reference", "The repository has corrupted index files", "The remote origin has been deleted", "A merge conflict has aborted"], correct_index=0, explanation="Detached HEAD means you are viewing a specific commit point, not an active branch pointer."),
        QuizQuestion(id="git_i3", skill="Git", difficulty="Intermediate", question="What does `git reset --soft HEAD~1` do?", options=["Deletes the commit and discards all changes", "Undoes the last commit but leaves changes staged in the index", "Undoes the commit and discards staged changes but keeps working directory", "Pushes a revert to remote"], correct_index=1, explanation="--soft moves the branch pointer back while keeping changes in the staging index."),
        QuizQuestion(id="git_i4", skill="Git", difficulty="Intermediate", question="What command temporarily shelves uncommitted local modifications without committing?", options=["git stash", "git save", "git pause", "git shelf"], correct_index=0, explanation="git stash records working directory state and reverts to clean HEAD."),
        QuizQuestion(id="git_i5", skill="Git", difficulty="Intermediate", question="What is the purpose of `git cherry-pick <commit>`?", options=["Deletes a specific commit from history", "Applies the exact diff of an existing commit from another branch onto current HEAD", "Reverts a pull request", "Tags a commit for release"], correct_index=1, explanation="cherry-pick copies an individual commit's changes onto the current branch."),
        QuizQuestion(id="git_a1", skill="Git", difficulty="Advanced", question="How does Git internally store and represent file content?", options=["Diffs and delta patches exclusively", "Content-addressable SHA/object store using Blobs, Trees, and Commits", "Flat SQLite database", "Compressed zip archives per branch"], correct_index=1, explanation="Git is a content-addressable object store indexing blobs (files), trees (directories), and commits by hash."),
        QuizQuestion(id="git_a2", skill="Git", difficulty="Advanced", question="What safety mechanism allows recovering commits that were orphaned by hard reset or rebase?", options=["git reflog", "git restore-all", "git fsck --clean", "git undelete"], correct_index=0, explanation="git reflog records every update to HEAD, allowing checkout and recovery of orphaned commit hashes."),
        QuizQuestion(id="git_a3", skill="Git", difficulty="Advanced", question="What does the `-w -M -C` flag combination do when running `git blame`?", options=["Ignores whitespace changes (-w) and detects moved (-M) or copied (-C) lines from other files or commits", "Wipes commit messages and compresses data", "Enables multithreaded blame calculation", "Generates web UI reports"], correct_index=0, explanation="-w ignores formatting; -M detects moved lines; -C detects copied lines across files."),
        QuizQuestion(id="git_a4", skill="Git", difficulty="Advanced", question="What is a 'Three-Way Merge' base in Git conflict resolution?", options=["The most recent common ancestor commit of the two branches being merged", "The remote HEAD commit", "The root initial commit", "A temporary user-created tag"], correct_index=0, explanation="A 3-way merge compares Branch A, Branch B, and their nearest common ancestor merge-base."),
        QuizQuestion(id="git_a5", skill="Git", difficulty="Advanced", question="What does `git bisect` automate using binary search?", options=["Finding the specific commit that introduced a bug between a known good and bad commit", "Splitting large commits into smaller ones", "Sorting commit logs by date", "Balancing git repository disk usage"], correct_index=0, explanation="git bisect performs binary search across commits to pinpoint regressions quickly.")
    ]
}

def _generate_generic_questions(skill: str) -> List[QuizQuestion]:
    """
    Generates realistic, tailored technical challenge questions for any claimed language/skill
    not explicitly pre-coded in SAMPLE_QUIZZES (e.g. Go, Rust, Java, C++, Ruby, etc.).
    """
    s = skill.strip()
    return [
        QuizQuestion(
            id=f"{s.lower()}_b1", skill=s, difficulty="Basic",
            question=f"What is the primary compilation/execution model of {s}?",
            options=[
                f"Standard idiomatic runtime/execution environment for {s}",
                "Interpreted exclusively via browser JavaScript engine",
                "Direct FPGA hardware microcode only",
                "Non-deterministic quantum simulation"
            ],
            correct_index=0,
            explanation=f"{s} uses its standard language runtime and compilation model."
        ),
        QuizQuestion(
            id=f"{s.lower()}_b2", skill=s, difficulty="Basic",
            question=f"How are dependencies and libraries typically managed in modern {s} projects?",
            options=[
                f"Using standard official package management tools for {s}",
                "Copying raw C source files manually into the kernel",
                "Dependencies cannot be used in {s}",
                "Editing binary hex bytes directly"
            ],
            correct_index=0,
            explanation=f"Modern {s} ecosystems use official package and module managers."
        ),
        QuizQuestion(
            id=f"{s.lower()}_b3", skill=s, difficulty="Basic",
            question=f"What is the standard error-handling mechanism recommended in {s}?",
            options=[
                f"Idiomatic error handling patterns established in {s} documentation",
                "Ignoring all errors and continuing execution silently",
                "Terminating OS kernel on any warning",
                "Writing errors to physical punch cards"
            ],
            correct_index=0,
            explanation=f"Idiomatic error handling in {s} guarantees predictable failure recovery."
        ),
        QuizQuestion(
            id=f"{s.lower()}_b4", skill=s, difficulty="Basic",
            question=f"Which naming and formatting convention is standard in {s}?",
            options=[
                f"Official community style guides and automated formatters for {s}",
                "Random alternating capitalization",
                "Encoding code in base64 strings only",
                "Single-letter variable names across all files"
            ],
            correct_index=0,
            explanation=f"Standard style guides and linters maintain code readability in {s}."
        ),
        QuizQuestion(
            id=f"{s.lower()}_b5", skill=s, difficulty="Basic",
            question=f"What command or tool executes the automated test suite in a {s} codebase?",
            options=[
                f"The standard test runner and assertion framework for {s}",
                "Restarting the computer repeatedly",
                "Printing code to paper",
                "Running rm -rf on the source tree"
            ],
            correct_index=0,
            explanation=f"{s} codebases run unit tests using the ecosystem's standard test runner."
        ),
        QuizQuestion(
            id=f"{s.lower()}_i1", skill=s, difficulty="Intermediate",
            question=f"How does {s} handle memory management and object lifecycles?",
            options=[
                f"Through {s}'s defined memory model (e.g. GC, ownership, or manual allocation)",
                "Allocating all variables on GPU registers only",
                "Writing all variables into swap files on disk",
                "Memory is never freed in {s}"
            ],
            correct_index=0,
            explanation=f"{s} manages memory through its language-level architecture rules."
        ),
        QuizQuestion(
            id=f"{s.lower()}_i2", skill=s, difficulty="Intermediate",
            question=f"How does concurrency or asynchronous I/O typically operate in {s}?",
            options=[
                f"Using {s}'s native concurrency primitives (e.g. threads, coroutines, or channels)",
                "Executing only one instruction per day",
                "Disabling hardware clocks",
                "Forking independent operating systems"
            ],
            correct_index=0,
            explanation=f"{s} concurrency models enable safe parallel or non-blocking I/O execution."
        ),
        QuizQuestion(
            id="gen_i3", skill=s, difficulty="Intermediate",
            question=f"What pattern is best practice for separating business logic from I/O in {s}?",
            options=[
                "Layered or modular architecture with interfaces and dependency inversion",
                "Writing entire applications in a single global variable",
                "Hardcoding credentials and database connections directly in controllers",
                "Storing code in cookie headers"
            ],
            correct_index=0,
            explanation="Modular separation of concerns ensures testability and maintainability."
        ),
        QuizQuestion(
            id="gen_i4", skill=s, difficulty="Intermediate",
            question=f"What is the recommended practice for handling configuration and secrets in {s}?",
            options=[
                "Environment variables or secret managers accessed at runtime",
                "Hardcoding plaintext API keys in public repositories",
                "Embedding passwords in compiled binary comments",
                "Sending secrets over unencrypted HTTP GET parameters"
            ],
            correct_index=0,
            explanation="12-Factor principles dictate storing configuration in environment variables."
        ),
        QuizQuestion(
            id="gen_i5", skill="Intermediate", difficulty="Intermediate",
            question=f"How do you profile and diagnose CPU or memory bottlenecks in {s}?",
            options=[
                f"Using standard profilers and flame graphs designed for {s}",
                "Guessing randomly and deleting files",
                "Adding random sleep statements across code",
                "Overclocking the monitor refresh rate"
            ],
            correct_index=0,
            explanation="Deterministic profiling surfaces exact call stacks responsible for latency."
        ),
        QuizQuestion(
            id="gen_a1", skill=s, difficulty="Advanced",
            question=f"What security defense should be implemented against injection vulnerabilities in {s}?",
            options=[
                "Parameterized queries, input sanitization, and strict schema validation",
                "Concatenating raw user strings directly into commands",
                "Disabling TLS certificate verification",
                "Granting administrative root permissions to public endpoints"
            ],
            correct_index=0,
            explanation="Parameterized statements and schema validation mitigate injection vectors."
        ),
        QuizQuestion(
            id="gen_a2", skill=s, difficulty="Advanced",
            question=f"In high-throughput microservices built with {s}, how should downstream failures be handled?",
            options=[
                "Circuit breakers, exponential backoff with jitter, and dead-letter queues",
                "Retrying in an infinite tight loop without timeouts",
                "Crashing the entire server cluster immediately",
                "Dropping customer database tables"
            ],
            correct_index=0,
            explanation="Circuit breakers and exponential backoff prevent cascading thundering-herd outages."
        ),
        QuizQuestion(
            id="gen_a3", skill=s, difficulty="Advanced",
            question=f"How do distributed systems coordinate state safely when using {s}?",
            options=[
                "Idempotency keys, transactional outboxes, and distributed consensus (Raft/Paxos)",
                "Assuming network calls never fail or duplicate",
                "Shared global memory across remote servers",
                "Random sleep timers"
            ],
            correct_index=0,
            explanation="Idempotency and transactional outboxes guarantee at-least-once message delivery safety."
        ),
        QuizQuestion(
            id="gen_a4", skill=s, difficulty="Advanced",
            question=f"What is the impact of excessive lock contention in concurrent {s} applications?",
            options=[
                "Thread starvation, reduced throughput, and latency spikes",
                "Automatic compiler optimization",
                "Faster database queries",
                "Decreased network bandwidth usage"
            ],
            correct_index=0,
            explanation="Lock contention causes thread serialization and severe throughput degradation."
        ),
        QuizQuestion(
            id="gen_a5", skill=s, difficulty="Advanced",
            question=f"What is the optimal CI/CD testing strategy for production {s} codebases?",
            options=[
                "Automated unit, integration, and lint checks running in parallel with coverage gates",
                "Manual testing directly on live production databases",
                "Skipping tests when release deadlines are tight",
                "Committing code without running build tools"
            ],
            correct_index=0,
            explanation="Automated CI pipelines enforce regressions checks before any deployment."
        )
    ]

class QuestionBankEngine:
    def get_questions_for_skill(self, skill: str) -> List[QuizQuestion]:
        # Exact skill match only: a Python quiz must never grade a Java (or any other) claim
        norm = normalize_skill(skill)
        if norm in SAMPLE_QUIZZES:
            return SAMPLE_QUIZZES[norm]
        # Match case-insensitively
        for k, q_list in SAMPLE_QUIZZES.items():
            if k.lower() == norm.lower():
                return q_list
        return []


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
