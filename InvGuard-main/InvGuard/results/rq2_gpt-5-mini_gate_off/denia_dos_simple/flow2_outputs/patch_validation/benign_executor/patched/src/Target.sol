/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_simple.sol
 * @author: -
 * @vulnerable_at_lines: 17,18
 */


pragma solidity ^0.4.25;

contract DosOneFunc {

    address[] listAddresses;
    mapping(address => uint256) public payments;
    uint256 public virtualLength;
    bool private _locked;

    function ifillArray() public returns (bool){
        require(!_locked);
        _locked = true;

        if(virtualLength < 1500) {
            // Convert push-loop to pull-payment pattern:
            // record amount owed to msg.sender instead of pushing in a loop (avoids DoS from a reverting recipient)
            // each original push is now represented as "350" units owed for this caller
            // update state before any external calls and guard against overflow
            require(virtualLength + 350 >= virtualLength);
            payments[msg.sender] += 350;
            virtualLength += 350;

            _locked = false;
            return true;

        } else {
            // reset virtualLength and keep original behavior of clearing the stored array
            virtualLength = 0;
            listAddresses = new address[](0);
            _locked = false;
            return false;
        }
    }

    // Allow recipients to withdraw their recorded payments (pull-payment)
    function withdrawPayments() public returns (bool) {
        require(!_locked);
        _locked = true;

        uint256 payment = payments[msg.sender];
        require(payment > 0);

        // State update before external call (CEI) and zero-out to prevent reentrancy issues
        payments[msg.sender] = 0;

        // Use require on send so failure propagates per policy
        require(msg.sender.send(payment));

        _locked = false;
        return true;
    }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `DosOneFunc` has a no-arg constructor (or implicit constructor).
contract Target is DosOneFunc {
    constructor() DosOneFunc() {}
}
