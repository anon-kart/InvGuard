pragma solidity ^0.8.20;

contract GasRelayer {
    mapping(bytes32 => bool) public executed;

    event Relayed(bytes32 id, bool ok);

    function relay(address target, bytes calldata data, bytes32 id) external {
        require(!executed[id], "done");
        executed[id] = true;
        (bool ok, ) = target.call(data);
        emit Relayed(id, ok);
    }
}
