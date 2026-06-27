// Generates the synthetic serialization fixtures used by the golden tests.
//
// Each writeObject() call produces one ``<name>.ser`` file under the output
// directory (argv[0], default "."). The data is entirely synthetic -- no PII --
// so the resulting fixtures are safe to commit to a public repository.
//
// Regenerate with:  see tools/README.md  (needs a JDK; tested on Temurin 25 LTS).
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.Arrays;

public class GenerateFixtures {

    static void write(String dir, String name, Object o) throws IOException {
        try (ObjectOutputStream oos =
                new ObjectOutputStream(new FileOutputStream(dir + "/" + name + ".ser"))) {
            oos.writeObject(o);
        }
    }

    public static void main(String[] args) throws Exception {
        String dir = args.length > 0 ? args[0] : ".";

        // All primitive field types + a String reference field.
        write(dir, "prims", new Prims());

        // Inheritance: a superClassDesc chain with fields in both classes.
        write(dir, "inherit", new Derived());

        // Arrays: int[], byte[] (Value path), String[] / int[][] (Values path).
        write(dir, "arrays", new Holder());

        // An enum constant: TC_ENUM.
        write(dir, "enumv", new EnumHolder());

        // ArrayList: a custom writeObject => objectAnnotation / TC_BLOCKDATA.
        ArrayList<String> list = new ArrayList<>();
        list.add("x");
        list.add("y");
        write(dir, "arraylist", list);

        // The same String instance twice => a TC_REFERENCE back-reference.
        String shared = "shared";
        write(dir, "refs", new Object[] {shared, shared});

        // A String longer than 65535 bytes => TC_LONGSTRING.
        char[] big = new char[70000];
        Arrays.fill(big, 'Z');
        write(dir, "longstring", new String(big));

        // Arrays of every primitive type (the non-byte[] "Values" path).
        write(dir, "primarrays", new PrimArrays());

        // Edge-case floating point: scientific-notation boundaries, signed zero,
        // NaN/Infinity. (Extreme subnormals like *.MIN_VALUE are omitted: Java
        // itself does not emit shortest digits for them.)
        write(dir, "floats", new Floats());

        // A java.lang.Class object => TC_CLASS.
        write(dir, "classobj", String.class);

        // A dynamic proxy => TC_PROXYCLASSDESC.
        Object proxy =
                Proxy.newProxyInstance(
                        GenerateFixtures.class.getClassLoader(),
                        new Class<?>[] {Greeter.class},
                        new Handler());
        write(dir, "proxy", proxy);

        // NOTE: TC_RESET / TC_EXCEPTION are not produced here -- the reference
        // jar does not support them, so they cannot be golden-tested against it.
        // They are covered by hand-verified tests in tests/test_protocol.py.
    }
}

class Prims implements Serializable {
    private static final long serialVersionUID = 1L;
    byte b = -5;
    char c = 'Q';
    double d = 123.45;
    float f = 1.5f;
    int i = 1000000;
    long l = -1L;
    short s = -2;
    boolean flag = true;
    String name = "hello";
}

class Base implements Serializable {
    private static final long serialVersionUID = 1L;
    int baseField = 7;
}

class Derived extends Base {
    private static final long serialVersionUID = 1L;
    String tag = "derived";
}

class Holder implements Serializable {
    private static final long serialVersionUID = 1L;
    int[] ints = {1, 2, 3};
    byte[] bytes = {10, 20, 30};
    String[] strs = {"a", "b"};
    int[][] grid = {{1}, {2, 3}};
}

enum Color {
    RED,
    GREEN,
    BLUE
}

interface Greeter extends Serializable {
    String greet();
}

class Handler implements InvocationHandler, Serializable {
    private static final long serialVersionUID = 1L;

    public Object invoke(Object proxy, Method method, Object[] args) {
        return "hi";
    }
}

class EnumHolder implements Serializable {
    private static final long serialVersionUID = 1L;
    Color color = Color.GREEN;
}

class PrimArrays implements Serializable {
    private static final long serialVersionUID = 1L;
    double[] doubles = {1.5, 2.5};
    long[] longs = {1L, -1L};
    boolean[] bools = {true, false};
    char[] chars = {'A', 'B'};
    short[] shorts = {1, -1};
    float[] floats = {1.5f};
}

class Floats implements Serializable {
    private static final long serialVersionUID = 1L;
    double[] doubles = {
        0.0, -0.0, 1.0, 2.5, 123.45, 1e6, 1e7, 0.001, 1e-4, 1e20, 1.5e-10,
        1.0 / 3.0, 0.1, Double.MAX_VALUE,
        Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY,
    };
    float[] floats = {
        0.0f, -0.0f, 1.0f, 0.1f, 1e8f, 1e-5f, 1.0f / 3.0f, Float.MAX_VALUE,
        Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY,
    };
}
