// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface Vm {
    function deal(address who, uint256 newBalance) external;
    function prank(address sender) external;
    function startPrank(address sender) external;
    function stopPrank() external;
    function snapshot() external returns (uint256);
    function revertTo(uint256 id) external returns (bool);
    function expectRevert() external;
    function expectRevert(bytes calldata revertData) external;
}

contract Test {
    Vm public constant vm =
        Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    event log_named_uint(string key, uint256 val);
    event log_named_bytes(string key, bytes val);
    event log_named_int(string key, int256 val);
    event log_named_address(string key, address val);
    event log_named_string(string key, string val);
}
