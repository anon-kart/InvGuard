pragma solidity ^0.4.24;

contract NameRegistrar {
    bool public unlocked = false;
    address public registrar;

    struct NameRecord {
        bytes32 name;
        address mappedAddress;
    }

    mapping(bytes32 => address) public resolve;

    constructor() public {
        registrar = msg.sender;
    }

    function register(bytes32 _name, address _mappedAddress) public {
        NameRecord newRecord;
        newRecord.name = _name;
        newRecord.mappedAddress = _mappedAddress;
        resolve[_name] = _mappedAddress;
        require(unlocked);
    }
}
