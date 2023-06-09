## prototype for an alternate approach to structured constants

from abc import abstractmethod

from typing import Any, Dict, Generator, Generic, Optional, Sequence, Union
from typing_extensions import Annotated, Literal, Protocol, Type, TypeVar

from pylaborate.common_staging.naming import get_module, ModuleArg

## tests
from assertpy import assert_that


## Descriptors at detail
## https://docs.python.org/3/howto/descriptor.html


def merge_mro(bases: Sequence[Type]) -> Generator[Type, None, None]:
    ## utility for predicting a method resolution order, given
    ## the base classes of a class being initialized
    found = []
    for cls in bases:
        for mrocls in cls.__mro__:
            if mrocls in found:
                found.remove(mrocls)
            found.append(mrocls)
    for cls in found:
        yield cls


T = TypeVar("T")


class ProtocolError(Exception):
    pass


class Field(Generic[T]):
    """generic class for read-only field descriptors"""

    ## Implementation note: If this class provides no __set__ method,
    ## Python will still allow the descriptor field to be set within
    ## the containing class/instance - at which point, it might then
    ## become a normal attribute value.

    def __init__(self, value: T):
        self._value = value
        self._originating_class = None
        self._containing_class = None
        self._name = None
        ## TBD usage cases for string type annotations
        ## and typing.Annotation annotations
        ##  - https://docs.python.org/3/howto/annotations.html
        ##  - python-language-server [PyPI] x vs code (OSS)
        ##  - runtime module/class/object browsing x runtime reflection
        ##  - Python x Qt @ Desktop | Python x Electron in vs code
        self._annotation = None

    def dup(self):
        new = self.__class__(self._value)
        new.originating_class = self.originating_class
        new.name = self.name
        annot = self.annotation
        if annot:
            new.annotation = annot
        return new

    def __set_name__(self, owner, name: str):
        containing = self.containing_class
        if (not containing) or (owner is containing):
            ## Implementation Note: If self.containing_class is not yet
            ## initialized, it may be that this is being called during
            ## class initialization ...
            self._name = name
        else:
            # fmt: off
            raise ProtocolError(
                "Cannot set name for non-containing class %s in field %s of %s" % (
                    owner, self, containing
                )
            )
            # fmt: on

    def __get__(self, obj, objtype=None) -> T:
        return self._value

    @property
    def name(self) -> Union[str, None]:
        return self._name

    @name.setter
    def name(self, new_value: str):
        ## Note: Not thread-safe in initializing self.name
        name = self._name
        if name and new_value != name:
            # fmt: off
            raise ProtocolError(
                "Name already initialized in %s" % self,
                self, name, new_value
            )
            # fmt: on
        else:
            assert isinstance(new_value, str), "new_value is not a string"
            self._name = new_value

    @property
    def originating_class(self) -> Union[type, None, Literal[False]]:
        ## implementations can override the Field.originating_class initialization
        ## used within the FieldClass __new__ method, by setting the initial
        ## originating_class of a Field descriptor to False
        ##
        ## (FIXME that has not been tested in application)
        return self._originating_class

    @originating_class.setter
    def originating_class(self, new_value: Type):
        orig = self._originating_class
        ## Note: Not thread-safe in initializing self.originating_class
        if orig and (new_value is not orig):
            # fmt: off
            raise ProtocolError(
                "Originating class already initialized in %s" % self,
                self, orig, new_value
            )
            # fmt: on
        else:
            assert isinstance(new_value, type), "new_value is not a type"
            self._originating_class = new_value

    @property
    def containing_class(self) -> Union[type, None, Literal[False]]:
        ## Implementation note: See atove, concerning the usage of a False
        ## value for the containing_class property of a Field descriptor
        return self._containing_class

    @containing_class.setter
    def containing_class(self, new_value: Type):
        orig = self._containing_class
        ## Note: Not thread-safe in initializing self.containing_class
        if orig and (new_value is not orig):
            # fmt: off
            raise ProtocolError(
                "Containing class already initialized in %s" % self,
                self, orig, new_value
            )
            # fmt: on
        else:
            assert isinstance(new_value, type), "new_value is not a type"
            self._containing_class = new_value

    @property
    def annotation(self):
        return self._annotation

    @annotation.setter
    def annotation(self, value):
        ## this will unconditionally set the value
        self._annotation = value

    def __str__(self):
        cont = self.containing_class
        if cont:
            cont = cont.__name__
        else:
            ## e.g "<None>" or "<False>"
            cont = "<" + str(cont) + ">"

        name = self.name
        if name:
            name = str(name)
        else:
            ## e.g "<None>" if no name has been initialized
            ## - visible during FieldClass initialization
            name = "<" + str(name) + ">"

        annot = self.annotation
        annotstr = ""
        if annot:
            if isinstance(annot, Annotated):
                annot = annot.__origin__
            anname = annotstr
            if isinstance(annot, type):
                anname = annot.__name__
            elif isinstance(annot, str):
                anname = annot
            else:
                anname = str(annot)
            annotstr = " [" + anname + "]"

        # fmt: off
        return "<%s %s::%s%s at 0x%x>" % (
            self.__class__.__name__, cont, name, annotstr, id(self)
        )
        # fmt: on

    def __repr__(self):
        return str(self)


## FIXME Define Field descriptor subclasses each implementing descriptor __set__
## - ReadOnlyField decriptor
## - WriteOnceField descriptor
## - MutableField descriptor, also implementing __delete__


class ArgumentError(Exception):
    ## an alternative to ValueError, for some set of argument values
    ##
    ## This exception class provides __init__, __repr__ and __str__ methods
    ## accepting keyword arguments. Any keyword arguments will be presented
    ## as features of the exception condition, within the __repr__ and __str__
    ## methods
    ##
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self._kwargs = kwargs

    @property
    def kwargs(self) -> Dict:
        return self._kwargs

    def __str__(self):
        ## return a string in a syntax similar to the Exception.__str__(),
        ## including a string presentation for each value from the initizlied
        ## args and kwargs
        argstr = ", ".join((str(a) for a in self.args))
        kwargs = self.kwargs
        if len(kwargs) == 0:
            kwargstr = ""
        else:
            kwargstr = ", " + ", ".join((k + "=" + str(kwargs[k]) for k in kwargs))
        return "(" + argstr + kwargstr + ")"

    def __repr__(self):
        ## return a repr string using the class qualname and the repr presentation
        ## for each value from the initizlied args and kwargs - structurally similar
        ## to Exception.__repr__()
        argstr = ", ".join((repr(a) for a in self.args))
        kwargs = self.kwargs
        if len(kwargs) == 0:
            kwargstr = ""
        else:
            kwargstr = ", " + ", ".join((k + "=" + repr(kwargs[k]) for k in kwargs))
        return self.__class__.__qualname__ + "(" + argstr + kwargstr + ")"


def is_descriptor(obj) -> bool:
    ## generalized predicate method for determining whether an object represents
    ## a descriptor object
    ##
    ## Known limitations
    ## - while this method will check for the presence of any __get__, __set__,
    ##   or __delete__ attribute in the object, it will not check to ensure that
    ##   any coresponding attribute value is callable
    return (
        hasattr(obj, "__get__") or hasattr(obj, "__set__") or hasattr(obj, "__delete__")
    )


def get_descriptor(cls: Type, name: str, default=None) -> Any:
    ## utility for accessing a descriptor reference from within a defined class
    ##
    ## ## Usage
    ##
    ## If the `cls` object contains an entry in the object's `__dict__` map
    ## matching `name` and if the value under that name is a descriptor
    ## object, returns the descriptor object, else returns the `default` value
    ##
    ## ## Exceptions
    ##
    ## - raises TypeError if the `cls` object cannot contain a descriptor,
    ##   i.e if the object does not define a `__dict__` attribute
    ##
    ## ## Implementation Notes
    ##
    ## It's assumed that any object accessible within a class' `__dict__`
    ## map and defining one or more of a `__get__`,  `__set__` or
    ## `__delete__` attribute would represent a descriptor object
    ##
    if hasattr(cls, "__dict__"):
        varmap = vars(cls)
        if name in varmap:
            val = varmap[name]
            if is_descriptor(val):
                return val
        return default
    else:
        raise TypeError("object cannot contain a descriptor: %s" % cls, cls)


T = TypeVar("T")


class DescriptorType(Protocol[T]):
    ## for practical extents, this implementation stipulates that a DescriptorType
    ## must implement at least a __get__ method
    @abstractmethod
    def __get__(self, obj, objtype=None) -> T:
        raise NotImplementedError("__get__ not implemented in %s" % repr(self), self)


class FieldClass(type):
    """Generic metaclass for field classes"""

    @property
    def derived_from(self) -> Union[None, Type]:
        ## utility acessor for reflection under @fieldclass applications
        if hasattr(self, "_derived_from"):
            return self._derived_from

    def __new__(cls: Type, name: str, bases: Sequence, dct: Dict):
        ## Concept: Within a FieldClass, fold all non-dunder/non_private attr decls
        ## into a Field descriptor

        newdct = dict()

        if "derived_from" in dct:
            ## moving the derived_from value from the implicit public namespace
            ## of the class' dict value, to where it can be accessed by the
            ## derived_from property reader
            ##
            ## Implementation notes:
            ## - not directly related to an application of FieldType.derive()
            ## - implemented primarily as a feature in relation to the
            ##   @fieldclass decorator
            ## - mainly used for keeping track of the class that the @fieldclass
            ##   decorator was applied to, before the class will be shadowed
            ##   during FieldClass initialization in the module under which
            ##   the decorated class was initially defined
            derived = dct["derived_from"]
            dct.pop("derived_from")
            newdct["_derived_from"] = derived

        ## collection of field descriptors, used internally
        descriptors = {}

        ## descriptors to configure after class init
        configure_descriptors = []

        for attr in dct:
            if attr.startswith("_"):
                ## Caveat: neither dunder not _private attributes will be overridden
                ## with a Field descriptor
                continue
            fieldval = dct[attr]
            if is_descriptor(fieldval):
                ## Caveat; each existing descriptor initialized from the class
                ## description will be used as-is, not overridden with a Field
                ## descriptor
                ##
                ## For a provided descriptor `fdesc` of type `Field` such that
                ## fdesc.originating_class is not the value False, the descriptor
                ## will be further initialized after the class is created. This
                ## may allow for a deferred initialization of Field descriptors
                ## created directly within a class description.
                ##
                ## If fdesc.originating_class is False, the Field descriptor
                ## fdesc will not be further initialized
                ##
                if isinstance(fieldval, Field) and (
                    fieldval.originating_class is not False
                ):
                    descriptors[attr] = fieldval
                    configure_descriptors.append(fieldval)
            else:
                field = Field(fieldval)
                newdct[attr] = field
                descriptors[attr] = field
                configure_descriptors.append(field)

        field_annot = {}
        if "__annotations__" in dct:
            cls_annot = dct["__annotations__"]
            for attr in descriptors:
                if attr in cls_annot and attr not in field_annot:
                    field_annot[attr] = cls_annot[attr]

        for basc in bases:
            ## ensure inheritance (through dup) of non-shadowed Field descriptors
            bdct = basc.__dict__
            annotations = None
            for attr in bdct:
                val = bdct[attr]
                if attr == "__annotations__":
                    annotations = val
                elif isinstance(val, Field) and attr not in newdct:
                    desc_dup = val.dup()
                    newdct[attr] = desc_dup
                    descriptors[attr] = desc_dup
                    configure_descriptors.append(desc_dup)
            if annotations:
                for attr in annotations:
                    if (attr in descriptors) and (attr not in field_annot):
                        field_annot[attr] = annotations[attr]

        dct.update(newdct)
        cls_new = super().__new__(cls, name, bases, dct)

        for desc in configure_descriptors:
            desc.containing_class = cls_new
            if not desc.originating_class:
                desc.originating_class = cls_new
            name = desc.name
            if name in field_annot:
                desc.annotation = field_annot[name]
        return cls_new


class FieldType:
    ## FIXME Move the __new__ method below to a ConstantFields(FieldType...) class
    def __new__(cls: Type, *args, **kwargs):
        ## concept: Return the original FieldType class from the class' constructor,
        ## thus implementing a singleton FieldType with the class object itself
        ##
        ## Implementation Notes:
        ##
        ## - While this could construct and return a new subclass of cls, the resulting
        ##   anonymous class would never be garbage collected.
        ##
        ## - The derive() method has been defined for purpose of explicitly creating
        ##   a new derived instance of a FieldType class, with a provided class name
        ##
        ## - The present Field descriptor implementation does not provide any
        ##   guarding about field value setting. This should be subject to
        ##   revision ...
        ##
        ##  - This limits the implementation of any implementing class toa
        ##    singularly class-based form of object creation/object reference.
        ##    This limitation might be partially mitigated with the availability
        ##    of the derive() method. The concept was initially to implement a
        ##    sort of constant-fields class structure, ostensibly an alternative
        ##    to the Enum implementation in Python stdlib.
        ##
        if (len(args) != 0) or (len(kwargs) != 0):
            # fmt: off
            raise ArgumentError("FieldType constructor accepts no initialization arguments", *args, **kwargs)
            # fmt: on

        return cls

    @classmethod
    def derive(cls, name: str, **kwargs):
        ## Initialize a FieldType class deriving from this class as a base class
        ##
        ## syntax:
        ##
        ## name
        ## : name of the derived class
        ##
        ## kwargs
        ## : values to be used to provide the initial __dict__ of the derived class
        ##
        ## Usage
        ##
        ## ... using the provided class' metaclass as the metaclass of the derived class,
        ## and the provided class itself as the single base class of the derived class
        ##
        ## This would represent the recommended method for initializing a new instance/subclass
        ## of a FieldTest singleton class `cls``:
        ##
        ## > `cls.derive(name)``
        ##
        ## For purpose of reference, __module__ = <module_name> may be provided in kwargs
        ## e.g using __module__ = __name__ at point of call.
        ##
        ## When a __module__ name is provided in kwargs, the name of the derived class will be
        ## used to initialize an attribute value referencing the derived class, within the named
        ## module.
        ##
        if "__qualname__" not in kwargs:
            kwargs["__qualname__"] = name
        bases = (cls,)
        new = cls.__class__(name, bases, kwargs)
        if "__module__" in kwargs:
            modname = kwargs["__module__"]
            assert isinstance(modname, str), "__module__ value should be a string"
            m = get_module(modname)
            ## TBD does this actually work ...
            setattr(m, new.__name__, new)
        return new


def fieldclass(
    # fmt: off
    cls: Type,
    metaclass: Type[FieldClass] = FieldClass,
    module: ModuleArg = None
    # fmt: on
) -> FieldClass:
    ## decorator for FieldClass initialization
    ##
    ## Tested only insofar as for deriving a class from a decorated FieldClass
    ##
    ## This prototype does not yet support decoration of a class definiing
    ## any one or more methods - tested only insofar as for an Enum-like API
    ##
    ## FIXME
    ## - the metaclass kwarg would be used only when annotating a non-
    ##   FieldType class
    ##
    ## - ! update the FieldClass.__new__ impl to also avoid creating
    ##   a descriptor for any callable attributes
    ##
    ## TBD
    ## - add a kwarg no_wrap: Sequence[str] allowing the caller to
    ##   provide a list of attribute names for attributes that should
    ##   not be implemented with a Field descriptor
    ##
    ## Implementation Note:
    ##
    ## The FieldClass __new__ method will initialize a Field descriptor
    ## for each non-decriptor attribute of the cls, such that each
    ## descriptor-interfaced attribute would have a name not starting
    ## with "_"
    ##

    assert isinstance(cls, type), "@fieldclass was provided with a non-class object"
    mdlname = get_module(module if module else cls.__module__).__name__
    name = cls.__name__
    if isinstance(cls, FieldClass) and issubclass(cls, FieldType):
        return cls.derive(name, __module__=mdlname, derived_from=cls)
    else:
        ## FIXME this represents a substantially different call semantics
        ## and has not been tested as yet
        # fmt: off
        return metaclass(name, (cls, FieldType,), dict(__module__ = mdlname, derived_from = cls))
        # fmt: on


##
## test cases
##


class FieldTest(metaclass=FieldClass):
    ## unused for purpose of test. Illustration only.
    ##
    ## Each subclass of FieldClass should use a FieldType class as a direct or indirect base class.
    ##
    ## This policy will not be strictly enforced in the FieldClass __new__ initializer
    pass


class FieldTypeTest(FieldType, metaclass=FieldClass):
    field_a: int = 15


class FieldTypeSubtest(FieldTypeTest, metaclass=FieldClass):
    field_b: int = -15
    ## TBD descriptor protocol @ compatibility with type linters
    field_c = Field(0)


@fieldclass
class FieldClassDecoratorTest(FieldTypeSubtest):
    field_d: str = "Thunk"


def each_field_descriptor(cls):
    dct = cls.__dict__
    for attr in dct:
        val = dct[attr]
        if isinstance(val, Field):
            yield val


def test_field_type_test():
    assert_that(hasattr(FieldTypeTest, "field_a")).is_true()
    ## ensure normal Field descriptor value initialization
    assert_that(FieldTypeTest.field_a).is_equal_to(15)

    dtors_fttest = tuple((f.name for f in each_field_descriptor(FieldTypeTest)))
    assert_that("field_a" in dtors_fttest).is_true()
    desc_a = FieldTypeTest.__dict__["field_a"]
    ## ensure normal Field descriptor initialization
    assert_that(desc_a.originating_class).is_equal_to(FieldTypeTest)
    assert_that(desc_a.containing_class).is_equal_to(FieldTypeTest)
    ## ensure any annotation is carried into the field descriptor
    assert_that(desc_a.annotation).is_equal_to(int)


def test_field_type_subtest():
    ## ensure Field descriptor inheritance
    assert_that(hasattr(FieldTypeSubtest, "field_a")).is_true()
    ## ensure value
    assert_that(FieldTypeSubtest.field_b).is_equal_to(-15)

    ## ensure initialization
    assert_that(hasattr(FieldTypeSubtest, "field_b")).is_true()
    ## ensure value
    assert_that(FieldTypeSubtest.field_a).is_equal_to(15)

    ## ensure initialization
    assert_that(hasattr(FieldTypeSubtest, "field_c")).is_true()
    ## ensure value
    assert_that(FieldTypeSubtest.field_c).is_equal_to(0)

    sub_dtors = tuple((f.name for f in each_field_descriptor(FieldTypeSubtest)))
    assert_that("field_a" in sub_dtors).is_true()
    assert_that("field_b" in sub_dtors).is_true()
    assert_that("field_c" in sub_dtors).is_true()

    sub_desc_a = FieldTypeSubtest.__dict__["field_a"]
    sub_desc_b = FieldTypeSubtest.__dict__["field_b"]
    sub_desc_c = FieldTypeSubtest.__dict__["field_c"]

    ## ensure initialization of a Field descriptor inherited from a base class
    assert_that(sub_desc_a.originating_class).is_equal_to(FieldTypeTest)
    assert_that(sub_desc_a.containing_class).is_equal_to(FieldTypeSubtest)

    ## ensure normal Field descriptor initialization
    assert_that(sub_desc_b.originating_class).is_equal_to(FieldTypeSubtest)
    assert_that(sub_desc_b.containing_class).is_equal_to(FieldTypeSubtest)

    ## ensure initialization of a directly provided Field descriptor
    assert_that(sub_desc_c.originating_class).is_equal_to(FieldTypeSubtest)
    assert_that(sub_desc_c.containing_class).is_equal_to(FieldTypeSubtest)

    ## ensure propogration of annotations through dup/inheritance
    assert_that(sub_desc_a.annotation).is_equal_to(int)

    ## ensure FieldType constructor => singleton semantics
    assert_that(FieldTypeTest() is FieldTypeTest).is_true()
    assert_that(FieldTypeSubtest() is FieldTypeSubtest).is_true()


def test_field_class_derive():
    this_module = get_module(__name__)
    if hasattr(this_module, "DerivedFieldTypeTest"):
        ## cleanup for interactive eval
        delattr(this_module, "DerivedFieldTypeTest")

    ## ensure operation of the derive() method
    derived = FieldTypeTest.derive("DerivedFieldTypeTest", __module__=__name__)

    assert_that(derived.__name__).is_equal_to("DerivedFieldTypeTest")
    assert_that(hasattr(derived, "field_a")).is_true()
    ## ensure field values are inherited via derive()
    assert_that(derived.field_a).is_equal_to(15)
    ## ensure field descriptors are inherited via derive()
    derived_dtors = tuple((f.name for f in each_field_descriptor(derived)))
    assert_that("field_a" in derived_dtors).is_true()
    derived_field_a = derived.__dict__["field_a"]
    ## ensure descriptors are initailized via derive()
    assert_that(derived_field_a.originating_class).is_equal_to(FieldTypeTest)
    assert_that(derived_field_a.containing_class).is_equal_to(derived)
    ## ensure the derived class is bound under the denoted module, via derive()
    assert_that(hasattr(this_module, "DerivedFieldTypeTest")).is_true()


def test_fieldclass_decorator_func():
    ##
    ## tests for the @fieldclass decorator function
    ##
    ## Implementation notes
    ## - By side effect, the following 'fieldclass' call will modify
    ##   the testing environment
    ##
    ## - The recommended way to use the fieldclass function would be
    ##   as a decorator called immediately after class initialization.
    ##
    ## - This test stores a back reference to the decorated class,
    ##   before calling the fieldclass decorator function on that class.
    ##   The back-reference may be used independent of the fc.derived_from
    ##   property, for purpose of tetss.
    initial_ftt = FieldTypeTest
    derived_fc = fieldclass(initial_ftt)

    ## ensure that a back-reference was stored by the decorator function
    assert_that(derived_fc.derived_from is initial_ftt).is_true()

    ## ensure field_type.derive() was used for @fieldclass(field_type)
    derived_fc_bases = derived_fc.__bases__
    assert_that(len(derived_fc_bases)).is_equal_to(1)
    assert_that((derived_fc_bases)[0] is initial_ftt).is_true()
    assert_that(derived_fc.__class__ is FieldClass).is_true()

    ## ensure that the initial class and the derived class are not the same class,
    ## though having an equivalent name
    assert_that(derived_fc is initial_ftt).is_false()
    assert_that(derived_fc.__name__).is_equal_to(initial_ftt.__name__)

    ## ensure that the class produced by @fieldclass will be bound for the same name
    ## under the module of the class on which the @fieldclass was derived - in effect,
    ## shadowing the initial class within that module
    derived_fc_module = get_module(derived_fc.__module__)
    assert_that(derived_fc_module is get_module(initial_ftt.__module__)).is_true()
    assert_that(hasattr(derived_fc_module, derived_fc.__name__)).is_true()
    assert_that(getattr(derived_fc_module, derived_fc.__name__) is derived_fc).is_true()

    assert_that(hasattr(derived_fc, "field_a")).is_true()
    ## ensure field values are inherited via fieldclass() -> derive()
    assert_that(derived_fc.field_a).is_equal_to(15)
    ## ensure field descriptors are inherited via fieldclass() -> derive()
    derived_fc_dtors = dict(([f.name, f] for f in each_field_descriptor(derived_fc)))
    assert_that("field_a" in derived_fc_dtors).is_true()
    derived_fc_field_a = derived_fc_dtors["field_a"]
    ## ensure descriptors are initailized via fieldclass() -> derive()
    assert_that(derived_fc_field_a.originating_class).is_equal_to(initial_ftt)
    assert_that(derived_fc_field_a.containing_class).is_equal_to(derived_fc)
    ## ensure the derived_fc class is bound under the denoted module, via fieldclass() -> derive()
    this_module = get_module(__name__)
    assert_that(hasattr(this_module, "DerivedFieldTypeTest")).is_true()

    ## test for the actual decorator application
    assert_that(hasattr(FieldClassDecoratorTest, "derived_from")).is_true()
    assert_that(len(FieldClassDecoratorTest.__bases__)).is_equal_to(1)
    assert_that(FieldClassDecoratorTest.__bases__[0]).is_equal_to(
        FieldClassDecoratorTest.derived_from
    )

    decorated_dtors = tuple(
        (f.name for f in each_field_descriptor(FieldClassDecoratorTest))
    )
    assert_that("field_a" in decorated_dtors).is_true()
    assert_that("field_b" in decorated_dtors).is_true()
    assert_that("field_c" in decorated_dtors).is_true()
    assert_that("field_d" in decorated_dtors).is_true()
    assert_that(FieldClassDecoratorTest.field_a).is_equal_to(FieldTypeTest.field_a)
    assert_that(FieldClassDecoratorTest.field_b).is_equal_to(FieldTypeSubtest.field_b)
    assert_that(FieldClassDecoratorTest.field_c).is_equal_to(FieldTypeSubtest.field_c)
    assert_that(FieldClassDecoratorTest.field_d).is_equal_to(FieldClassDecoratorTest.derived_from.field_d)

    ## restoring the initial class binding within the testing environment
    ## - note that the derived_fc may still not be garbage collected,
    ##   while it's referenced as a subclass of some other class
    setattr(get_module(__name__), initial_ftt.__name__, initial_ftt)


## FIXME develop a more complex example of multiple inheritance
## among FieldType classes, for purpose of testing the usage
## of merge_mro above

## FIXME also test the @fieldclass decorator function when decorating
## a non-FieldType class


if __name__ == "__main__":
    test_field_type_test()
    test_field_type_subtest()
    test_field_class_derive()
    test_fieldclass_decorator_func()
