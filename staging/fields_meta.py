## prototype for an alternate approach to structured constants

from abc import abstractmethod

from typing import Any, Dict, Generator, Generic, Optional, Sequence, Union
from typing_extensions import Annotated, Literal, Protocol, Type, TypeVar

from pylaborate.common_staging.naming import get_module, ModuleArg

## tests
from assertpy import assert_that
from types import ModuleType
import sys


## Descriptors at detail
## https://docs.python.org/3/howto/descriptor.html


def gen_class_info(cls):
    ## prototype for predicting the method resolution order
    ## of a single class
    ##
    ## defined before merge_mro()
    ##
    ## used initially for predicting the method resolution order
    ## for a new class, given a set of base classes
    ##
    ## does not actually use the class' method resolution order
    ##
    ## produces a list value sequentially equivalent to a class'
    ## method resolution order under cls.__mro__
    ##
    ## no known instances where this generator produces
    ## a sequence not equivalent to the cls' MRO
    ##
    ## the general remove-and-append methodology developed here is
    ## also used in merge_mro
    ##
    if cls is object:
        yield cls
    else:
        bases = cls.__bases__
        found = [cls]
        for b in bases:
            for nxtc in gen_class_info(b):
                if nxtc in found:
                    found.remove(nxtc)
                found.append(nxtc)
        for it in found:
            yield it


def merge_mro(bases: Sequence[Type]) -> Generator[Type, None, None]:
    ## utility for predicting a method resolution order, given
    ## the base classes of a class being initialized
    ##
    ## contrasted to the gen_class_info prototype, above,
    ## this will use the actual __mro__ of each class.
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
        self.value = value
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
        new = self.__class__(self.value)
        new.originating_class = self.originating_class
        new.name = self.name
        annot = self.annotation
        if annot:
            new.annotation = annot
        return new

    def __set_name__(self, owner, name: str):
        cont = self.containing_class
        if (not cont) or (owner is cont):
            ## Implementation Note: If self.containing_class is not yet
            ## initialized, it may be that this is being called during
            ## class initialization ...
            self._name = name
        else:
            # fmt: off
            raise ProtocolError(
                "Cannot __set__name__() for non-containing class %s in field %s of %s" % (
                    owner, self, cont
                )
            )
            # fmt: on

    def __get__(self, obj, objtype=None) -> T:
        return self.value

    @property
    def name(self) -> Union[str, None]:
        return self._name

    @name.setter
    def name(self, new_value: str):
        ## Note: Not thread-safe in initializing self.name
        name = self._name
        if name and new_value != name:
            # fmt: off
            raise ValueError(
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
            raise ValueError(
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
            raise ValueError(
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
## - MutableField desctiptor, also implementing __delete__


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
    def descriptors(self) -> Dict[str, DescriptorType]:
        return self._descriptors

    @property
    def derived_from(self) -> Union[None, Type]:
        ## utility acessor for reflection under @fieldclass applications
        if hasattr(self, "_derived_from"):
            return self._derived_from

    def __new__(cls: Type, name: str, bases: Sequence, dct: Dict):
        ## - Resolved: how are descriptors actually stored in a class?
        ##    see cls.__dict__ && get_descriptor()
        ## - Resolved (??) Within a FieldClass, fold all non-dunder/non_private
        ##    attr decls from dct into a Field descriptor
        ##   - ... for each ostensible attr value that is not a descriptor already
        ##   - Implemented below, pursaunt towards an initial usage test
        print(f"new FieldClass: {cls} {name} {bases} {dct}")
        ## Implementation Note:
        ##   attr types are provided via an '__annotations__'  value in dct

        newdct = dict()

        if "_descriptors" in dct:
            descriptors = dct["_descriptors"].copy()
        else:
            descriptors = {}

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
                descriptors[attr] = fieldval
                if isinstance(fieldval, Field) and (
                    fieldval.originating_class is not False
                ):
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
                d = descriptors[attr]
                if isinstance(d, Field):
                    if attr in cls_annot and attr not in field_annot:
                        field_annot[attr] = cls_annot[attr]

        for basc in merge_mro(bases):
            ## ensure inheritance (through dup) of non-shadowed Field descriptors
            ##
            ## FIXME remove the _descriptors attribute storage here
            ## - for each name in basc.__dict__ where `get_descriptor(basc, name)``
            ##   returns a truthy value, assume that the value is a descriptor
            ## - if the value is a Field descriptor, then handle as below,
            ##   otherwise discard the value locally
            ## - note that the present implementation would iterate across the
            ##   complete method resolution order, given the set of base classes.
            ##
            ##   This depth of iteration was implemented before the definition
            ##   of get_descriptor(). It may not be necessary if using
            ##   get_descriptor() across the __dict__ of each immediate
            ##   base class.
            ##
            ## - This should be revised to limit to operations on Field
            ##   descriptors, such that should normally be inherited across
            ##   each subclass having a FieldClass metaclass
            ##
            ## - This update will require some modification of the test cases,
            ##   defined below
            ##
            if hasattr(basc, "_descriptors"):
                dtors = getattr(basc, "_descriptors")
                for attr in dtors:
                    desc = dtors[attr]
                    if isinstance(desc, Field) and not (attr in descriptors):
                        desc_dup = desc.dup()
                        descriptors[attr] = desc_dup
                        configure_descriptors.append(desc_dup)
                if hasattr(basc, "__annotations__"):
                    ## transpose the first corresponding annotation from each base (MRO) class
                    basc_annot = basc.__annotations__
                    for attr in descriptors:
                        if attr not in field_annot and attr in basc_annot:
                            field_annot[attr] = basc_annot[attr]

        ## FIXME there may be some temporary wastage here, for annotations in `field_annot`
        ## not annotating any Field descriptor to configure - see implementation notes, above

        newdct["_descriptors"] = descriptors

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


def test_fields_meta_a():

    assert_that(hasattr(FieldTypeTest, "field_a")).is_true()
    ## ensure normal Field descriptor value initialization
    assert_that(FieldTypeTest.field_a).is_equal_to(15)

    dtors_fttest = FieldTypeTest.descriptors
    assert_that("field_a" in dtors_fttest).is_true()
    desc_a = dtors_fttest["field_a"]
    ## ensure normal Field descriptor initialization
    assert_that(desc_a.originating_class).is_equal_to(FieldTypeTest)
    assert_that(desc_a.containing_class).is_equal_to(FieldTypeTest)
    ## ensure any annotation is carried into the field descriptor
    assert_that(desc_a.annotation).is_equal_to(int)

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

    sub_dtors = FieldTypeSubtest.descriptors
    assert_that("field_a" in sub_dtors).is_true()
    assert_that("field_b" in sub_dtors).is_true()
    assert_that("field_c" in sub_dtors).is_true()

    sub_desc_a = sub_dtors["field_a"]
    sub_desc_b = sub_dtors["field_b"]
    sub_desc_c = sub_dtors["field_c"]

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

    ## ensure operation of the derive() method
    this_module = get_module(__name__)
    if hasattr(this_module, "DerivedFieldTypeTest"):
        ## thunk for usage in interactive eval
        delattr(this_module, "DerivedFieldTypeTest")

    derived = FieldTypeTest.derive("DerivedFieldTypeTest", __module__=__name__)

    assert_that(derived.__name__).is_equal_to("DerivedFieldTypeTest")
    assert_that(hasattr(derived, "field_a")).is_true()
    ## ensure field values are inherited via derive()
    assert_that(derived.field_a).is_equal_to(15)
    ## ensure field descriptors are inherited via derive()
    derived_dtors = derived.descriptors
    assert_that("field_a" in derived_dtors).is_true()
    derived_field_a = derived_dtors["field_a"]
    ## ensure descriptors are initailized via derive()
    assert_that(derived_field_a.originating_class).is_equal_to(FieldTypeTest)
    assert_that(derived_field_a.containing_class).is_equal_to(derived)
    ## ensure the derived class is bound under the denoted module, via derive()
    assert_that(hasattr(this_module, "DerivedFieldTypeTest")).is_true()

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
    derived_fc_dtors = derived_fc.descriptors
    assert_that("field_a" in derived_fc_dtors).is_true()
    derived_fc_field_a = derived_fc_dtors["field_a"]
    ## ensure descriptors are initailized via fieldclass() -> derive()
    assert_that(derived_fc_field_a.originating_class).is_equal_to(initial_ftt)
    assert_that(derived_fc_field_a.containing_class).is_equal_to(derived_fc)
    ## ensure the derived_fc class is bound under the denoted module, via fieldclass() -> derive()
    assert_that(hasattr(this_module, "DerivedFieldTypeTest")).is_true()

    ## restoring the initial class binding within the testing environment
    ## - note that the derived_fc may still not be garbage collected,
    ##   while it's referenced as a subclass of some other class
    setattr(get_module(__name__), initial_ftt.__name__, initial_ftt)

    ## FIXME develop a more complex example of multiple inheritance
    ## among FieldType classes, for purpose of testing the usage
    ## of merge_mro above

    ## FIXME also test the @fieldclass decorator function when decorating
    ## a non-FieldType class


def each_class(context=sys.modules, cache=[]):
    if id(context) not in cache:
        cache.append(id(context))
        match context:
            case type():
                yield context
                yield from each_class(context.__dict__, cache)
            case ModuleType():
                yield from each_class(context.__dict__, cache)
            case dict():
                for name in context:
                    yield from each_class(context[name], cache)


def test_gen_class_info():
    rslt = []
    failed = []
    for name in sys.modules:
        for cls in each_class(sys.modules[name]):
            try:
                if tuple(gen_class_info(cls)) != cls.__mro__:
                    rslt.append(cls)
            except Exception:
                failed.append(cls)
    if len(failed) != 0:
        print("! FAILED " + str(failed))
    if len(rslt) != 0:
        print("!= " + str(rslt))
    assert_that(len(rslt)).is_zero()

if __name__ == "__main__":
    test_fields_meta_a()
