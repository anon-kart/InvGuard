contract sGuard{
  bool internal locked_;
  constructor() internal {
    locked_ = false;
  }
  modifier nonReentrant_() {
    require(!locked_);
    locked_ = true;
    _;
    locked_ = false;
  }
}
pragma solidity ^0.5.8;

contract Target  is sGuard {

    mapping(address => uint) balances_re_ent1;

     function withdraw_balances_re_ent1 () nonReentrant_  public {
           (bool success,) =msg.sender.call.value(balances_re_ent1[msg.sender ])("");
           if (success)
              balances_re_ent1[msg.sender] = 0;
          }

    function() external payable {}

    function deposit() public payable {}

}
